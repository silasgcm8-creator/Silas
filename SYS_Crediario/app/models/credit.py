"""Crediários (a compra parcelada em si)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.types import MoneyType
from app.models.base import Base, TimestampMixin
from app.utils.money import ZERO

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.installment import Installment


class Credit(Base, TimestampMixin):
    __tablename__ = "crediarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        sa.ForeignKey("clientes.id", ondelete="RESTRICT"), index=True
    )
    valor_total: Mapped[Decimal] = mapped_column(MoneyType)
    entrada: Mapped[Decimal] = mapped_column(MoneyType, default=ZERO)
    parcelas: Mapped[int] = mapped_column(sa.Integer)
    primeiro_vencimento: Mapped[date] = mapped_column(sa.Date, index=True)
    descricao: Mapped[str | None] = mapped_column(sa.String(200), nullable=True)
    criado_por_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )

    client: Mapped["Client"] = relationship(back_populates="credits")
    installments: Mapped[list["Installment"]] = relationship(
        back_populates="credit",
        cascade="all, delete-orphan",
        order_by="Installment.numero",
    )

    @property
    def valor_financiado(self) -> Decimal:
        return self.valor_total - self.entrada

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Credit #{self.id} {self.valor_total}>"
