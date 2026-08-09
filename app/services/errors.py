"""Erros de negócio com mensagens prontas para o usuário."""

from __future__ import annotations

from app.utils.validators import ValidationError


class BusinessError(Exception):
    """Regra de negócio violada."""


class DuplicateClientError(BusinessError):
    """CPF já cadastrado."""


class NotFoundError(BusinessError):
    """Registro inexistente."""


__all__ = [
    "BusinessError",
    "DuplicateClientError",
    "NotFoundError",
    "ValidationError",
]
