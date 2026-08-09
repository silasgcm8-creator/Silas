"""Contas de recebimento cadastradas pelo administrador.

Os dados bancários **nunca** são inventados pelo sistema: eles só existem aqui
porque o administrador os digitou. O funcionário apenas escolhe uma conta já
autorizada na hora de emitir a cobrança.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

#: Tipos de conta aceitos no cadastro.
ACCOUNT_TYPES = ("Corrente", "Poupança", "Pagamento")

#: Tipos de chave Pix, conforme o padrão do Banco Central.
PIX_KEY_TYPES = ("CPF", "CNPJ", "E-mail", "Telefone", "Aleatória")


class BankAccount(Base):
    __tablename__ = "contas_bancarias"
    __table_args__ = (
        sa.Index("ix_contas_ativa_nome", "ativa", "identificacao"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    #: Nome curto que o funcionário vê na lista ("Banco Principal", "PIX Loja").
    identificacao: Mapped[str] = mapped_column(sa.String(60), unique=True)

    banco_nome: Mapped[str] = mapped_column(sa.String(80), default="")
    banco_codigo: Mapped[str] = mapped_column(sa.String(10), default="")
    agencia: Mapped[str] = mapped_column(sa.String(10), default="")
    agencia_digito: Mapped[str] = mapped_column(sa.String(2), default="")
    conta: Mapped[str] = mapped_column(sa.String(20), default="")
    conta_digito: Mapped[str] = mapped_column(sa.String(2), default="")
    tipo_conta: Mapped[str] = mapped_column(sa.String(20), default="")

    beneficiario_nome: Mapped[str] = mapped_column(sa.String(120), default="")
    beneficiario_documento: Mapped[str] = mapped_column(sa.String(20), default="")

    pix_chave: Mapped[str] = mapped_column(sa.String(140), default="")
    pix_tipo: Mapped[str] = mapped_column(sa.String(20), default="")

    #: Campos usados apenas por cobrança registrada em banco (quando houver
    #: integração oficial). Ficam vazios até então.
    carteira: Mapped[str] = mapped_column(sa.String(20), default="")
    convenio: Mapped[str] = mapped_column(sa.String(30), default="")
    codigo_beneficiario: Mapped[str] = mapped_column(sa.String(30), default="")

    ativa: Mapped[bool] = mapped_column(sa.Boolean, default=True, index=True)
    criado_em: Mapped[datetime] = mapped_column(sa.DateTime, default=datetime.now)
    atualizado_em: Mapped[datetime] = mapped_column(
        sa.DateTime, default=datetime.now, onupdate=datetime.now
    )

    @property
    def agencia_completa(self) -> str:
        if not self.agencia:
            return ""
        return f"{self.agencia}-{self.agencia_digito}" if self.agencia_digito else self.agencia

    @property
    def conta_completa(self) -> str:
        if not self.conta:
            return ""
        return f"{self.conta}-{self.conta_digito}" if self.conta_digito else self.conta

    @property
    def banco_completo(self) -> str:
        if self.banco_codigo and self.banco_nome:
            return f"{self.banco_codigo} — {self.banco_nome}"
        return self.banco_nome or self.banco_codigo

    @property
    def tem_dados_bancarios(self) -> bool:
        return bool(self.banco_nome or self.banco_codigo or self.conta)

    @property
    def tem_pix(self) -> bool:
        return bool(self.pix_chave)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BankAccount {self.identificacao}>"
