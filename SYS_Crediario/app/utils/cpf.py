"""Validação, normalização e máscara de CPF."""

from __future__ import annotations

import re

_NON_DIGITS = re.compile(r"\D")


def only_digits(value: str | None) -> str:
    return _NON_DIGITS.sub("", value or "")


def format_cpf(value: str | None) -> str:
    """Aplica a máscara 000.000.000-00 de forma progressiva."""
    digits = only_digits(value)[:11]
    if len(digits) <= 3:
        return digits
    if len(digits) <= 6:
        return f"{digits[:3]}.{digits[3:]}"
    if len(digits) <= 9:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:]}"
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


def _check_digit(digits: str, weight: int) -> int:
    total = sum(int(d) * (weight - i) for i, d in enumerate(digits))
    remainder = (total * 10) % 11
    return 0 if remainder == 10 else remainder


def is_valid_cpf(value: str | None) -> bool:
    digits = only_digits(value)
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    if _check_digit(digits[:9], 10) != int(digits[9]):
        return False
    return _check_digit(digits[:10], 11) == int(digits[10])


def normalize_cpf(value: str | None) -> str:
    """Forma canônica gravada no banco (com máscara, tamanho fixo)."""
    digits = only_digits(value)
    if len(digits) != 11:
        raise ValueError("CPF deve conter 11 dígitos.")
    return format_cpf(digits)
