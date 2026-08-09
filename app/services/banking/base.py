"""Contratos da integração bancária."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


class IntegrationNotConfigured(Exception):
    """Modalidade que depende de banco, sem integração oficial disponível."""


@dataclass(frozen=True)
class RegisteredBoleto:
    """Dados que **somente a instituição financeira** pode fornecer.

    Nenhum destes campos é calculado pelo sistema: todos vêm da resposta da API
    oficial do banco. Sem integração, este objeto nunca é criado.
    """

    nosso_numero: str
    linha_digitavel: str
    codigo_barras: str
    identificador_banco: str
    qrcode_pagamento: str
    status_bancario: str
    vencimento: date
    valor: Decimal
    pago_em: date | None = None
    valor_recebido: Decimal | None = None


class BankProvider(ABC):
    """Provedor de serviços de um banco ou instituição de pagamento."""

    nome: str = "provedor"

    @abstractmethod
    def disponivel(self) -> bool:
        """Indica se há credencial e contrato configurados."""

    def exigir_disponivel(self) -> None:
        if not self.disponivel():
            raise IntegrationNotConfigured(
                f"A integração com {self.nome} não está configurada. "
                "A cobrança registrada em banco só pode ser emitida através da "
                "API oficial da instituição financeira — o sistema não gera "
                "linha digitável nem código de barras por conta própria."
            )


class PixProvider(BankProvider):
    """Cobrança Pix com identificador registrado (Pix cobrança)."""

    nome = "Pix registrado"

    def disponivel(self) -> bool:
        return False


class BoletoProvider(BankProvider):
    """Boleto bancário registrado."""

    nome = "boleto bancário registrado"

    def disponivel(self) -> bool:
        return False

    def emitir(self, **dados: object) -> RegisteredBoleto:  # noqa: ARG002
        """Emite o título no banco. Sem integração, recusa de forma explícita."""
        self.exigir_disponivel()
        raise NotImplementedError  # pragma: no cover - inalcançável hoje

    def consultar(self, nosso_numero: str) -> RegisteredBoleto:  # noqa: ARG002
        self.exigir_disponivel()
        raise NotImplementedError  # pragma: no cover - inalcançável hoje
