"""Log de atividades — rastreabilidade das operações sensíveis."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LogAction(str):
    """Ações registradas (string simples para permitir extensão futura)."""

    CLIENT_CREATED = "CLIENTE_CRIADO"
    CLIENT_UPDATED = "CLIENTE_EDITADO"
    CLIENT_DELETED = "CLIENTE_EXCLUIDO"
    CLIENT_RESTORED = "CLIENTE_REATIVADO"
    CREDIT_CREATED = "CREDIARIO_CRIADO"
    INSTALLMENT_PAID = "PARCELA_PAGA"
    PAYMENT_REVERSED = "PAGAMENTO_ESTORNADO"
    RECEIPT_ISSUED = "COMPROVANTE_EMITIDO"
    SLIP_ISSUED = "CARNE_EMITIDO"
    CHARGE_ISSUED = "COBRANCA_EMITIDA"
    COMPANY_UPDATED = "EMPRESA_ATUALIZADA"
    INTEGRITY_CHECK = "BANCO_VERIFICADO"
    BACKUP_CREATED = "BACKUP_CRIADO"
    BACKUP_RESTORED = "BACKUP_RESTAURADO"
    USER_CREATED = "USUARIO_CRIADO"
    USER_UPDATED = "USUARIO_EDITADO"
    LOGIN = "LOGIN"
    LOGIN_FAILED = "LOGIN_FALHOU"
    API_STARTED = "API_INICIADA"
    API_STOPPED = "API_ENCERRADA"


class ActivityLog(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    usuario_nome: Mapped[str] = mapped_column(sa.String(120), default="sistema")
    acao: Mapped[str] = mapped_column(sa.String(40), index=True)
    detalhes: Mapped[str | None] = mapped_column(sa.String(400), nullable=True)
    cliente_id: Mapped[int | None] = mapped_column(sa.Integer, nullable=True, index=True)
    crediario_id: Mapped[int | None] = mapped_column(sa.Integer, nullable=True, index=True)
    parcela_id: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        sa.DateTime, default=datetime.now, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Log {self.acao} {self.criado_em:%d/%m/%Y %H:%M}>"
