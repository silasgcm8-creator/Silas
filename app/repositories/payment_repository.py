"""Consultas de recebimentos."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa

from app.database.types import sum_cents
from app.models.client import Client
from app.models.credit import Credit
from app.models.installment import Installment
from app.models.payment import Payment
from app.repositories.base_repository import BaseRepository


#: Pagamento válido é o que não foi estornado. Toda consulta de caixa aplica
#: esta condição — um estorno esquecido aqui devolveria dinheiro ao caixa.
ACTIVE = Payment.estornado_em.is_(None)


class PaymentRepository(BaseRepository[Payment]):
    model = Payment

    def get_active_by_installment(self, installment_id: int) -> Payment | None:
        """Recebimento que vale hoje para a parcela (ignora os estornados)."""
        stmt = sa.select(Payment).where(Payment.parcela_id == installment_id, ACTIVE)
        return self.session.scalars(stmt).first()

    def history_by_installment(self, installment_id: int) -> Sequence[Payment]:
        """Todo o histórico da parcela, inclusive os pagamentos estornados."""
        stmt = (
            sa.select(Payment)
            .where(Payment.parcela_id == installment_id)
            .order_by(Payment.id)
        )
        return self.session.scalars(stmt).all()

    def get_by_code(self, codigo: str) -> Payment | None:
        stmt = sa.select(Payment).where(Payment.codigo == codigo)
        return self.session.scalars(stmt).first()

    def next_sequence_for_day(self, reference: date) -> int:
        """Próximo número sequencial do dia, usado no código da operação."""
        stmt = sa.select(sa.func.count()).select_from(Payment).where(
            Payment.data_pagamento == reference
        )
        return int(self.session.scalar(stmt) or 0) + 1

    def list_period(
        self,
        start: date,
        end: date,
        term: str = "",
        limit: int = 1000,
        usuario_id: int | None = None,
    ) -> Sequence[sa.Row]:
        """Recebimentos do período.

        ``usuario_id`` restringe o resultado às operações de um único operador —
        é assim que o funcionário confere o que ele mesmo recebeu sem enxergar o
        movimento de caixa da loja.
        """
        stmt = (
            sa.select(
                Payment.id,
                Payment.data_pagamento,
                Client.nome,
                Client.cpf,
                Installment.numero,
                Credit.parcelas,
                Payment.valor,
                Payment.crediario_id,
                Payment.usuario_nome,
                Payment.codigo,
                Payment.parcela_id,
                Payment.forma_pagamento,
                Payment.documento_id,
            )
            .select_from(Payment)
            .join(Client, Client.id == Payment.cliente_id)
            .join(Credit, Credit.id == Payment.crediario_id)
            .join(Installment, Installment.id == Payment.parcela_id)
            .where(Payment.data_pagamento.between(start, end), ACTIVE)
            .order_by(Payment.data_pagamento.desc(), Payment.id.desc())
            .limit(limit)
        )
        if usuario_id is not None:
            stmt = stmt.where(Payment.usuario_id == usuario_id)
        term = (term or "").strip()
        if term:
            like = f"%{term}%"
            stmt = stmt.where(sa.or_(Client.nome.ilike(like), Client.cpf.like(like)))
        return self.session.execute(stmt).all()

    def total_period(self, start: date, end: date) -> int:
        stmt = sa.select(sum_cents(Payment.valor)).where(
            Payment.data_pagamento.between(start, end), ACTIVE
        )
        return int(self.session.scalar(stmt) or 0)

    def receipt_data(self, payment_id: int) -> sa.Row | None:
        """Dados completos de um recebimento para emitir o comprovante."""
        stmt = (
            sa.select(
                Payment.id,
                Payment.codigo,
                Payment.valor,
                Payment.data_pagamento,
                Payment.criado_em,
                Payment.usuario_nome,
                Payment.forma_pagamento,
                Payment.documento_id,
                Payment.estornado_em,
                Client.nome.label("cliente"),
                Client.cpf,
                Client.telefone,
                Installment.numero,
                Installment.vencimento,
                Credit.parcelas,
                Credit.id.label("crediario_id"),
            )
            .select_from(Payment)
            .join(Client, Client.id == Payment.cliente_id)
            .join(Credit, Credit.id == Payment.crediario_id)
            .join(Installment, Installment.id == Payment.parcela_id)
            .where(Payment.id == payment_id)
        )
        return self.session.execute(stmt).first()
