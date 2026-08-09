"""Estornos de pagamento — o pagamento original nunca é apagado.

Dado financeiro não desaparece do histórico: o recebimento continua na tabela
`pagamentos` marcado com `estornado_em`, e o motivo, o autor e o momento do
estorno ficam registrados aqui.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.database.types import MoneyType
from app.models.base import Base


class PaymentReversal(Base):
    __tablename__ = "estornos"

    id: Mapped[int] = mapped_column(primary_key=True)
    pagamento_id: Mapped[int] = mapped_column(
        sa.ForeignKey("pagamentos.id", ondelete="CASCADE"), index=True
    )
    parcela_id: Mapped[int] = mapped_column(sa.Integer, index=True)
    crediario_id: Mapped[int] = mapped_column(sa.Integer, index=True)
    cliente_id: Mapped[int] = mapped_column(sa.Integer, index=True)

    #: Valor que saiu do caixa, copiado do pagamento original.
    valor: Mapped[Decimal] = mapped_column(MoneyType)
    #: Data do pagamento estornado, preservada para conferência de caixa.
    data_pagamento: Mapped[date] = mapped_column(sa.Date, index=True)
    #: Código da operação de pagamento estornada.
    pagamento_codigo: Mapped[str] = mapped_column(sa.String(24), default="")

    motivo: Mapped[str] = mapped_column(sa.String(300))
    usuario_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    usuario_nome: Mapped[str] = mapped_column(sa.String(120), default="sistema")
    criado_em: Mapped[datetime] = mapped_column(
        sa.DateTime, default=datetime.now, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PaymentReversal pagamento={self.pagamento_id} {self.valor}>"
