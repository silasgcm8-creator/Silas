"""Consultas de crediários."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import joinedload

from app.database.types import sum_cents
from app.models.client import Client
from app.models.credit import Credit
from app.models.installment import Installment
from app.repositories.base_repository import BaseRepository
from app.repositories.client_repository import client_search_filter


class CreditRepository(BaseRepository[Credit]):
    model = Credit

    def list_with_balances(
        self, term: str = "", reference: date | None = None, limit: int = 500
    ) -> Sequence[sa.Row]:
        reference = reference or date.today()
        open_value = sa.case((Installment.pago.is_(False), Installment.valor), else_=0)
        overdue_value = sa.case(
            (
                sa.and_(Installment.pago.is_(False), Installment.vencimento < reference),
                Installment.valor,
            ),
            else_=0,
        )
        paid_count = sa.case((Installment.pago.is_(True), 1), else_=0)
        stmt = (
            sa.select(
                Credit.id,
                Client.id.label("cliente_id"),
                Client.nome,
                Client.cpf,
                Client.telefone,
                Credit.valor_total,
                Credit.entrada,
                Credit.parcelas,
                Credit.criado_em,
                sum_cents(open_value).label("saldo"),
                sum_cents(overdue_value).label("vencido"),
                sa.func.sum(paid_count).label("pagas"),
            )
            .select_from(Credit)
            .join(Client, Client.id == Credit.cliente_id)
            .outerjoin(Installment, Installment.crediario_id == Credit.id)
            .group_by(Credit.id)
            .order_by(Credit.id.desc())
            .limit(limit)
        )
        condition = client_search_filter(term)
        if condition is not None:
            stmt = stmt.where(condition)
        return self.session.execute(stmt).all()

    def list_by_client(
        self, client_id: int, reference: date | None = None
    ) -> Sequence[sa.Row]:
        reference = reference or date.today()
        open_value = sa.case((Installment.pago.is_(False), Installment.valor), else_=0)
        paid_value = sa.case((Installment.pago.is_(True), Installment.valor), else_=0)
        overdue_value = sa.case(
            (
                sa.and_(Installment.pago.is_(False), Installment.vencimento < reference),
                Installment.valor,
            ),
            else_=0,
        )
        stmt = (
            sa.select(
                Credit.id,
                Credit.valor_total,
                Credit.entrada,
                Credit.parcelas,
                Credit.primeiro_vencimento,
                Credit.criado_em,
                sum_cents(open_value).label("saldo"),
                sum_cents(paid_value).label("pago"),
                sum_cents(overdue_value).label("vencido"),
            )
            .select_from(Credit)
            .outerjoin(Installment, Installment.crediario_id == Credit.id)
            .where(Credit.cliente_id == client_id)
            .group_by(Credit.id)
            .order_by(Credit.id.desc())
        )
        return self.session.execute(stmt).all()

    def get_with_client(self, credit_id: int) -> Credit | None:
        stmt = (
            sa.select(Credit)
            .where(Credit.id == credit_id)
            .options(joinedload(Credit.client))
        )
        return self.session.scalars(stmt).unique().first()
