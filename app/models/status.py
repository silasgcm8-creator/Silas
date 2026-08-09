"""Situações de parcela e papéis de usuário."""

from __future__ import annotations

from enum import Enum


class InstallmentStatus(str, Enum):
    PAID = "PAGO"
    OPEN = "EM ABERTO"
    LATE = "ATRASADO"

    @property
    def label(self) -> str:
        return self.value


class Role(str, Enum):
    ADMIN = "ADMINISTRADOR"
    STAFF = "FUNCIONARIO"

    @property
    def label(self) -> str:
        return "Administrador" if self is Role.ADMIN else "Funcionário"

    @classmethod
    def from_value(cls, value: str) -> "Role":
        try:
            return cls(str(value).upper())
        except ValueError:
            return cls.STAFF


class PaymentMethod(str, Enum):
    """Formas de recebimento aceitas no caixa."""

    CASH = "DINHEIRO"
    PIX = "PIX"
    DEBIT = "CARTAO_DEBITO"
    CREDIT = "CARTAO_CREDITO"
    TRANSFER = "TRANSFERENCIA"
    OTHER = "OUTRO"

    @property
    def label(self) -> str:
        return {
            PaymentMethod.CASH: "Dinheiro",
            PaymentMethod.PIX: "PIX",
            PaymentMethod.DEBIT: "Cartão de débito",
            PaymentMethod.CREDIT: "Cartão de crédito",
            PaymentMethod.TRANSFER: "Transferência",
            PaymentMethod.OTHER: "Outro",
        }[self]

    @classmethod
    def from_value(cls, value: str | None) -> "PaymentMethod":
        try:
            return cls(str(value or "").upper())
        except ValueError:
            return cls.CASH


#: Rótulo legível de uma forma gravada no banco (aceita valor desconhecido).
def payment_method_label(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return PaymentMethod(str(value).upper()).label
    except ValueError:
        return str(value)
