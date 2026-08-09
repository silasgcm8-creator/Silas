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


class PaymentRepository(BaseRepository[Payment]):
    model = Payment

    def get_by_installment(self, installment_id: int) -> Payment | None:
        stmt = sa.select(Payment).where(Payment.parcela_id == installment_id)
        return self.session.scalars(stmt).first()

    def delete_by_installment(self, installment_id: int) -> int:
        stmt = sa.delete(Payment).where(Payment.parcela_id == installment_id)
        return int(self.session.execute(stmt).rowcount or 0)

    def list_period(
        self, start: date, end: date, term: str = "", limit: int = 1000
    ) -> Sequence[sa.Row]:
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
            )
            .select_from(Payment)
            .join(Client, Client.id == Payment.cliente_id)
            .join(Credit, Credit.id == Payment.crediario_id)
            .join(Installment, Installment.id == Payment.parcela_id)
            .where(Payment.data_pagamento.between(start, end))
            .order_by(Payment.data_pagamento.desc(), Payment.id.desc())
            .limit(limit)
        )
        term = (term or "").strip()
        if term:
            like = f"%{term}%"
            stmt = stmt.where(sa.or_(Client.nome.ilike(like), Client.cpf.like(like)))
        return self.session.execute(stmt).all()

    def total_period(self, start: date, end: date) -> int:
        stmt = sa.select(sum_cents(Payment.valor)).where(
            Payment.data_pagamento.between(start, end)
        )
        return int(self.session.scalar(stmt) or 0)
