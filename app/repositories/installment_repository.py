"""Consultas de parcelas, atrasos e próximos vencimentos."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa

from app.database.types import sum_cents
from app.models.client import Client
from app.models.credit import Credit
from app.models.installment import Installment
from app.repositories.base_repository import BaseRepository

class InstallmentRepository(BaseRepository[Installment]):
    model = Installment

    def list_by_credit(self, credit_id: int) -> Sequence[Installment]:
        stmt = (
            sa.select(Installment)
            .where(Installment.crediario_id == credit_id)
            .order_by(Installment.numero)
        )
        return self.session.scalars(stmt).all()

    def upcoming(self, reference: date | None = None, limit: int = 15) -> Sequence[sa.Row]:
        reference = reference or date.today()
        stmt = (
            sa.select(
                Client.nome,
                Client.cpf,
                Client.telefone,
                Installment.vencimento,
                Installment.valor,
                Installment.numero,
                Credit.parcelas,
                Credit.id.label("crediario_id"),
            )
            .select_from(Installment)
            .join(Credit, Credit.id == Installment.crediario_id)
            .join(Client, Client.id == Credit.cliente_id)
            .where(Installment.pago.is_(False), Installment.vencimento >= reference)
            .order_by(Installment.vencimento, Client.nome)
            .limit(limit)
        )
        return self.session.execute(stmt).all()

    def recent_late(self, reference: date | None = None, limit: int = 15) -> Sequence[sa.Row]:
        reference = reference or date.today()
        stmt = (
            sa.select(
                Client.nome,
                Client.cpf,
                Installment.vencimento,
                Installment.valor,
                Credit.id.label("crediario_id"),
            )
            .select_from(Installment)
            .join(Credit, Credit.id == Installment.crediario_id)
            .join(Client, Client.id == Credit.cliente_id)
            .where(Installment.pago.is_(False), Installment.vencimento < reference)
            .order_by(Installment.vencimento.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).all()

    def late_by_client(
        self, reference: date | None = None, order: str = "maior_valor_vencido"
    ) -> Sequence[sa.Row]:
        """Um registro por cliente em atraso, com totais consolidados."""
        reference = reference or date.today()
        late = sa.and_(Installment.pago.is_(False), Installment.vencimento < reference)
        overdue_value = sa.case((late, Installment.valor), else_=0)
        overdue_count = sa.case((late, 1), else_=0)
        open_value = sa.case((Installment.pago.is_(False), Installment.valor), else_=0)
        oldest = sa.func.min(sa.case((late, Installment.vencimento), else_=None))

        stmt = (
            sa.select(
                Client.id,
                Client.nome,
                Client.cpf,
                Client.telefone,
                sum_cents(overdue_value).label("vencido"),
                sum_cents(open_value).label("saldo"),
                sa.func.sum(overdue_count).label("parcelas_vencidas"),
                oldest.label("vencimento_antigo"),
            )
            .select_from(Client)
            .join(Credit, Credit.cliente_id == Client.id)
            .join(Installment, Installment.crediario_id == Credit.id)
            .group_by(Client.id)
            .having(sa.func.sum(overdue_count) > 0)
        )

        orders = {
            "maior_valor_vencido": sa.desc(sa.literal_column("vencido")),
            "maior_saldo": sa.desc(sa.literal_column("saldo")),
            "maior_atraso": sa.asc(sa.literal_column("vencimento_antigo")),
            "vencimento_antigo": sa.asc(sa.literal_column("vencimento_antigo")),
            "nome": sa.asc(Client.nome),
        }
        stmt = stmt.order_by(orders.get(order, orders["maior_valor_vencido"]))
        return self.session.execute(stmt).all()

    def late_details(self, client_id: int, reference: date | None = None) -> Sequence[sa.Row]:
        reference = reference or date.today()
        stmt = (
            sa.select(
                Installment.id,
                Installment.numero,
                Installment.vencimento,
                Installment.valor,
                Credit.id.label("crediario_id"),
                Credit.parcelas,
            )
            .select_from(Installment)
            .join(Credit, Credit.id == Installment.crediario_id)
            .where(
                Credit.cliente_id == client_id,
                Installment.pago.is_(False),
                Installment.vencimento < reference,
            )
            .order_by(Installment.vencimento)
        )
        return self.session.execute(stmt).all()

    def due_today_total(self, reference: date | None = None) -> tuple[int, int]:
        reference = reference or date.today()
        stmt = sa.select(
            sa.func.count(Installment.id), sum_cents(Installment.valor)
        ).where(Installment.pago.is_(False), Installment.vencimento == reference)
        row = self.session.execute(stmt).one()
        return int(row[0] or 0), int(row[1] or 0)
