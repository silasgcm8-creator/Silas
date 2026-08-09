"""Recebimentos registrados (histórico de caixa)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.database.types import MoneyType
from app.models.base import Base

#: Nome do índice único de `parcela_id`, compartilhado com as migrações para que
#: bancos novos e bancos já existentes fiquem com exatamente a mesma estrutura.
UNIQUE_PAYMENT_INDEX = "uq_pagamento_parcela"


class Payment(Base):
    __tablename__ = "pagamentos"
    #: Uma parcela só pode ter um recebimento. É o que impede o caixa de contar
    #: o mesmo pagamento duas vezes quando o balcão e o celular registram a
    #: mesma parcela ao mesmo tempo.
    __table_args__ = (
        sa.Index(UNIQUE_PAYMENT_INDEX, "parcela_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    parcela_id: Mapped[int] = mapped_column(
        sa.ForeignKey("parcelas.id", ondelete="CASCADE")
    )
    crediario_id: Mapped[int] = mapped_column(
        sa.ForeignKey("crediarios.id", ondelete="CASCADE"), index=True
    )
    cliente_id: Mapped[int] = mapped_column(
        sa.ForeignKey("clientes.id", ondelete="RESTRICT"), index=True
    )
    valor: Mapped[Decimal] = mapped_column(MoneyType)
    data_pagamento: Mapped[date] = mapped_column(sa.Date, index=True)
    usuario_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    usuario_nome: Mapped[str] = mapped_column(sa.String(120), default="—")
    criado_em: Mapped[datetime] = mapped_column(sa.DateTime, default=datetime.now)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Payment parcela={self.parcela_id} {self.valor}>"
