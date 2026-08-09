"""Documentos de cobrança e seu histórico.

Um documento é sempre de **uma parcela**. A situação (EM ABERTO / PAGO /
ATRASADO) não é gravada: ela acompanha a parcela vinculada, para nunca ficar
divergente. O que se grava é o cancelamento, que é uma decisão registrada.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.types import MoneyType
from app.models.base import Base

#: Modalidades de cobrança.
TYPE_STORE = "LOJA"
TYPE_BANK = "BANCO_PIX"
TYPE_REGISTERED = "BOLETO_REGISTRADO"

CHARGE_TYPES = (TYPE_STORE, TYPE_BANK, TYPE_REGISTERED)

CHARGE_TYPE_LABELS = {
    TYPE_STORE: "Exclusivamente na Ótica Visão",
    TYPE_BANK: "Banco / PIX",
    TYPE_REGISTERED: "Boleto bancário registrado",
}

#: Situações possíveis do documento (derivadas, exceto CANCELADO).
STATUS_OPEN = "EM ABERTO"
STATUS_PAID = "PAGO"
STATUS_LATE = "ATRASADO"
STATUS_CANCELLED = "CANCELADO"

CHARGE_STATUSES = (STATUS_OPEN, STATUS_PAID, STATUS_LATE, STATUS_CANCELLED)

#: Uma parcela só pode ter um documento **ativo**; cancelar libera nova emissão.
UNIQUE_CHARGE_INDEX = "uq_cobranca_parcela"
ACTIVE_CHARGE_CONDITION = "cancelado_em IS NULL"


class ChargeDocument(Base):
    __tablename__ = "documentos_cobranca"
    __table_args__ = (
        sa.Index(
            UNIQUE_CHARGE_INDEX,
            "parcela_id",
            unique=True,
            sqlite_where=sa.text(ACTIVE_CHARGE_CONDITION),
            postgresql_where=sa.text(ACTIVE_CHARGE_CONDITION),
        ),
        sa.Index("ix_documentos_emissao_status", "emissao", "cancelado_em"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    #: Identificador interno impresso no documento e no QR (OV-000001).
    numero: Mapped[str] = mapped_column(sa.String(20), unique=True, index=True)
    tipo: Mapped[str] = mapped_column(sa.String(24), index=True)

    cliente_id: Mapped[int] = mapped_column(
        sa.ForeignKey("clientes.id", ondelete="RESTRICT"), index=True
    )
    crediario_id: Mapped[int] = mapped_column(
        sa.ForeignKey("crediarios.id", ondelete="CASCADE"), index=True
    )
    parcela_id: Mapped[int] = mapped_column(
        sa.ForeignKey("parcelas.id", ondelete="CASCADE")
    )

    emissao: Mapped[date] = mapped_column(sa.Date, index=True)
    vencimento: Mapped[date] = mapped_column(sa.Date, index=True)

    #: Valores congelados na emissão, para a reimpressão sair igual ao original.
    valor_original: Mapped[Decimal] = mapped_column(MoneyType)
    juros: Mapped[Decimal] = mapped_column(MoneyType, default=0)
    desconto: Mapped[Decimal] = mapped_column(MoneyType, default=0)
    valor_atualizado: Mapped[Decimal] = mapped_column(MoneyType)

    descricao: Mapped[str] = mapped_column(sa.String(160), default="")
    observacao: Mapped[str] = mapped_column(sa.String(300), default="")

    conta_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("contas_bancarias.id", ondelete="SET NULL"), nullable=True
    )
    conta: Mapped["BankAccount | None"] = relationship(lazy="joined")  # noqa: F821

    #: Último PDF gerado, para reabrir sem regerar.
    pdf_path: Mapped[str] = mapped_column(sa.String(400), default="")
    impressoes: Mapped[int] = mapped_column(sa.Integer, default=0)

    criado_por_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    criado_por_nome: Mapped[str] = mapped_column(sa.String(120), default="sistema")
    criado_em: Mapped[datetime] = mapped_column(sa.DateTime, default=datetime.now)

    cancelado_em: Mapped[datetime | None] = mapped_column(
        sa.DateTime, nullable=True, index=True
    )
    cancelado_por: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    motivo_cancelamento: Mapped[str | None] = mapped_column(sa.String(300), nullable=True)

    @property
    def cancelado(self) -> bool:
        return self.cancelado_em is not None

    @property
    def tipo_label(self) -> str:
        return CHARGE_TYPE_LABELS.get(self.tipo, self.tipo)

    def status(self, pago: bool, reference: date | None = None) -> str:
        """Situação do documento: segue a parcela, exceto quando cancelado."""
        if self.cancelado:
            return STATUS_CANCELLED
        if pago:
            return STATUS_PAID
        reference = reference or date.today()
        return STATUS_LATE if self.vencimento < reference else STATUS_OPEN

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ChargeDocument {self.numero} {self.tipo}>"


class ChargeEvent(Base):
    """Histórico do documento: emissão, impressões, cancelamento, pagamento."""

    __tablename__ = "documentos_historico"

    id: Mapped[int] = mapped_column(primary_key=True)
    documento_id: Mapped[int] = mapped_column(
        sa.ForeignKey("documentos_cobranca.id", ondelete="CASCADE"), index=True
    )
    evento: Mapped[str] = mapped_column(sa.String(30), index=True)
    detalhes: Mapped[str] = mapped_column(sa.String(300), default="")
    usuario_nome: Mapped[str] = mapped_column(sa.String(120), default="sistema")
    criado_em: Mapped[datetime] = mapped_column(
        sa.DateTime, default=datetime.now, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ChargeEvent {self.evento} doc={self.documento_id}>"


EVENT_CREATED = "EMITIDO"
EVENT_PRINTED = "IMPRESSO"
EVENT_REPRINTED = "REIMPRESSO"
EVENT_CANCELLED = "CANCELADO"
EVENT_PAID = "PAGAMENTO_REGISTRADO"
EVENT_REVERSED = "PAGAMENTO_ESTORNADO"
