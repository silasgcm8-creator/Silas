"""Consultas de estornos (auditoria financeira)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time

import sqlalchemy as sa

from app.database.types import sum_cents
from app.models.client import Client
from app.models.credit import Credit
from app.models.installment import Installment
from app.models.reversal import PaymentReversal
from app.repositories.base_repository import BaseRepository


def _day_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    """Intervalo em datetime cobrindo os dois dias inteiros."""
    return datetime.combine(start, time.min), datetime.combine(end, time.max)


class ReversalRepository(BaseRepository[PaymentReversal]):
    model = PaymentReversal

    def list_period(
        self, start: date, end: date, limit: int = 1000
    ) -> Sequence[sa.Row]:
        inicio, fim = _day_bounds(start, end)
        stmt = (
            sa.select(
                PaymentReversal.id,
                PaymentReversal.criado_em,
                Client.nome,
                Client.cpf,
                Installment.numero,
                Credit.parcelas,
                PaymentReversal.valor,
                PaymentReversal.data_pagamento,
                PaymentReversal.pagamento_codigo,
                PaymentReversal.motivo,
                PaymentReversal.usuario_nome,
            )
            .select_from(PaymentReversal)
            .join(Client, Client.id == PaymentReversal.cliente_id)
            .join(Credit, Credit.id == PaymentReversal.crediario_id)
            .join(Installment, Installment.id == PaymentReversal.parcela_id)
            .where(PaymentReversal.criado_em.between(inicio, fim))
            .order_by(PaymentReversal.criado_em.desc(), PaymentReversal.id.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).all()

    def total_period(self, start: date, end: date) -> int:
        inicio, fim = _day_bounds(start, end)
        stmt = sa.select(sum_cents(PaymentReversal.valor)).where(
            PaymentReversal.criado_em.between(inicio, fim)
        )
        return int(self.session.scalar(stmt) or 0)
