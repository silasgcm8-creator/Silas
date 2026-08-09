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
