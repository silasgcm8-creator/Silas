"""Segurança: senhas, autenticação e permissões."""

from app.security.authentication import (
    AuthenticationError,
    CurrentSession,
    SessionUser,
    current_session,
    token_store,
)
from app.security.password import hash_password, verify_password
from app.security.permissions import Permission, PermissionDenied, can, require

__all__ = [
    "AuthenticationError",
    "CurrentSession",
    "Permission",
    "PermissionDenied",
    "SessionUser",
    "can",
    "current_session",
    "hash_password",
    "require",
    "token_store",
    "verify_password",
]
