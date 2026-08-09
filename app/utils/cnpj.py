"""Validação e máscara de CNPJ, para o cadastro da empresa."""

from __future__ import annotations

from app.utils.cpf import only_digits

#: Pesos dos dois dígitos verificadores, conforme a regra da Receita Federal.
_WEIGHTS_FIRST = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_WEIGHTS_SECOND = (6,) + _WEIGHTS_FIRST


def format_cnpj(value: str | None) -> str:
    """Aplica a máscara 00.000.000/0000-00 de forma progressiva."""
    digits = only_digits(value)[:14]
    if len(digits) <= 2:
        return digits
    if len(digits) <= 5:
        return f"{digits[:2]}.{digits[2:]}"
    if len(digits) <= 8:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:]}"
    if len(digits) <= 12:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:]}"
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


def _check_digit(digits: str, weights: tuple[int, ...]) -> int:
    total = sum(int(d) * w for d, w in zip(digits, weights))
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


def is_valid_cnpj(value: str | None) -> bool:
    digits = only_digits(value)
    if len(digits) != 14 or digits == digits[0] * 14:
        return False
    if _check_digit(digits[:12], _WEIGHTS_FIRST) != int(digits[12]):
        return False
    return _check_digit(digits[:13], _WEIGHTS_SECOND) == int(digits[13])


def format_document(value: str | None) -> str:
    """Máscara automática: CPF com 11 dígitos, CNPJ com 14."""
    from app.utils.cpf import format_cpf

    digits = only_digits(value)
    return format_cnpj(digits) if len(digits) > 11 else format_cpf(digits)


def is_valid_document(value: str | None) -> bool:
    """Aceita CPF (pessoa física) ou CNPJ (pessoa jurídica)."""
    from app.utils.cpf import is_valid_cpf

    digits = only_digits(value)
    if len(digits) == 14:
        return is_valid_cnpj(digits)
    return is_valid_cpf(digits)
