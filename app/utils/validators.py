"""Validação de entrada compartilhada por interface, serviços e API."""

from __future__ import annotations

import re

from app.utils.cpf import is_valid_cpf, normalize_cpf, only_digits


class ValidationError(Exception):
    """Erro de validação com mensagem pronta para o usuário final."""


def validate_name(value: str | None) -> str:
    name = " ".join((value or "").split())
    if len(name) < 3:
        raise ValidationError("Informe o nome completo do cliente.")
    if not re.search(r"[A-Za-zÀ-ÿ]", name):
        raise ValidationError("O nome deve conter letras.")
    return name


def validate_cpf(value: str | None) -> str:
    if not is_valid_cpf(value):
        raise ValidationError("CPF inválido. Confira os números digitados.")
    return normalize_cpf(value)


def format_phone(value: str | None) -> str:
    digits = only_digits(value)[:11]
    if len(digits) <= 2:
        return digits
    if len(digits) <= 6:
        return f"({digits[:2]}) {digits[2:]}"
    if len(digits) <= 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"


def validate_phone(value: str | None) -> str:
    digits = only_digits(value)
    if len(digits) not in (10, 11):
        raise ValidationError("Telefone inválido. Informe DDD + número.")
    if digits[:2] < "11":
        raise ValidationError("DDD inválido.")
    return format_phone(digits)


def validate_username(value: str | None) -> str:
    username = (value or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9._-]{3,32}", username):
        raise ValidationError(
            "Usuário deve ter de 3 a 32 caracteres (letras, números, ponto, hífen)."
        )
    return username


def validate_password(value: str | None) -> str:
    password = value or ""
    if len(password) < 6:
        raise ValidationError("A senha deve ter no mínimo 6 caracteres.")
    return password


def validate_reversal_reason(value: str | None) -> str:
    """O motivo do estorno é obrigatório: é o que dá sentido ao histórico."""
    motivo = " ".join((value or "").split())
    if len(motivo) < 5:
        raise ValidationError(
            "Informe o motivo do estorno (no mínimo 5 caracteres). "
            "Ele fica registrado na auditoria."
        )
    return motivo[:300]


#: Cabe no campo do banco (VARCHAR(300)) e no rodapé do comprovante.
PAYMENT_NOTE_LIMIT = 300


def validate_payment_note(value: str | None) -> str:
    """Observação do caixa: opcional, mas normalizada e limitada.

    Diferente do motivo do estorno, não é obrigatória — o recebimento comum não
    precisa de justificativa. Espaços em excesso e quebras de linha são
    achatados para o texto caber em uma linha do comprovante.
    """
    return " ".join((value or "").split())[:PAYMENT_NOTE_LIMIT]


def validate_installment_count(value: object) -> int:
    try:
        count = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValidationError("Quantidade de parcelas inválida.") from exc
    if not 1 <= count <= 60:
        raise ValidationError("A quantidade de parcelas deve ficar entre 1 e 60.")
    return count
