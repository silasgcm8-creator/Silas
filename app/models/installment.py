"""Parcelas e cálculo automático de situação."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.types import MoneyType
from app.models.base import Base
from app.models.status import InstallmentStatus
from app.utils.dates import days_late

if TYPE_CHECKING:
    from app.models.credit import Credit


class Installment(Base):
    __tablename__ = "parcelas"
    __table_args__ = (
        sa.UniqueConstraint("crediario_id", "numero", name="uq_parcela_numero"),
        sa.Index("ix_parcelas_pago_vencimento", "pago", "vencimento"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    crediario_id: Mapped[int] = mapped_column(
        sa.ForeignKey("crediarios.id", ondelete="CASCADE"), index=True
    )
    numero: Mapped[int] = mapped_column(sa.Integer)
    vencimento: Mapped[date] = mapped_column(sa.Date, index=True)
    valor: Mapped[Decimal] = mapped_column(MoneyType)
    pago: Mapped[bool] = mapped_column(sa.Boolean, default=False, index=True)
    pago_em: Mapped[date | None] = mapped_column(sa.Date, nullable=True)

    credit: Mapped["Credit"] = relationship(back_populates="installments")

    def status(self, reference: date | None = None) -> InstallmentStatus:
        """Situação sempre derivada dos dados — nunca digitada pelo funcionário."""
        if self.pago:
            return InstallmentStatus.PAID
        reference = reference or date.today()
        if self.vencimento < reference:
            return InstallmentStatus.LATE
        return InstallmentStatus.OPEN

    def dias_atraso(self, reference: date | None = None) -> int:
        if self.pago:
            return 0
        return days_late(self.vencimento, reference)

    def status_label(self, reference: date | None = None) -> str:
        situacao = self.status(reference)
        if situacao is InstallmentStatus.LATE:
            return f"ATRASADO — {self.dias_atraso(reference)} dias"
        return situacao.label

    def rotulo(self, total: int | None = None) -> str:
        total = total if total is not None else (self.credit.parcelas if self.credit else 0)
        return f"{self.numero}/{total}"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Installment {self.numero} {self.vencimento} {self.valor}>"
