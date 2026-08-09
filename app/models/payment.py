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

#: Condição do índice: a unicidade vale apenas entre os pagamentos válidos, para
#: que uma parcela estornada possa receber um novo pagamento.
ACTIVE_PAYMENT_CONDITION = "estornado_em IS NULL"


class Payment(Base):
    __tablename__ = "pagamentos"
    #: Uma parcela só pode ter um recebimento **válido**. É o que impede o caixa
    #: de contar o mesmo pagamento duas vezes quando o balcão e o celular
    #: registram a mesma parcela ao mesmo tempo. Estornos ficam fora da
    #: condição, então a parcela volta a poder ser paga depois de um estorno.
    __table_args__ = (
        sa.Index(
            UNIQUE_PAYMENT_INDEX,
            "parcela_id",
            unique=True,
            sqlite_where=sa.text(ACTIVE_PAYMENT_CONDITION),
            postgresql_where=sa.text(ACTIVE_PAYMENT_CONDITION),
        ),
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

    #: Identificador da operação, impresso no comprovante do cliente.
    codigo: Mapped[str] = mapped_column(sa.String(24), default="", index=True)

    usuario_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    usuario_nome: Mapped[str] = mapped_column(sa.String(120), default="—")
    criado_em: Mapped[datetime] = mapped_column(sa.DateTime, default=datetime.now)

    #: Preenchido no estorno. O pagamento continua no histórico, apenas deixa de
    #: valer para o caixa — exclusão lógica, nunca DELETE.
    estornado_em: Mapped[datetime | None] = mapped_column(
        sa.DateTime, nullable=True, index=True
    )

    @property
    def estornado(self) -> bool:
        return self.estornado_em is not None

    def __repr__(self) -> str:  # pragma: no cover
        marca = " ESTORNADO" if self.estornado else ""
        return f"<Payment parcela={self.parcela_id} {self.valor}{marca}>"
