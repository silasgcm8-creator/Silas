"""Dependências compartilhadas pelas rotas."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from app.security.authentication import SessionUser, token_store
from app.security.permissions import Permission, can


def bearer_token(authorization: str = Header(default="")) -> str:
    """Devolve o token cru do cabeçalho — usado também para encerrar a sessão."""
    prefix, _, token = authorization.partition(" ")
    token = token.strip()
    if prefix.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Envie o token no cabeçalho Authorization: Bearer <token>.",
        )
    return token


def current_user(token: str = Depends(bearer_token)) -> SessionUser:
    """Extrai o usuário a partir do token Bearer."""
    user = token_store.resolve(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão expirada. Entre novamente.",
        )
    return user


def require_permission(permission: Permission):  # noqa: ANN201
    def dependency(user: SessionUser = Depends(current_user)) -> SessionUser:
        if not can(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seu usuário não possui permissão para esta ação.",
            )
        return user

    return dependency
