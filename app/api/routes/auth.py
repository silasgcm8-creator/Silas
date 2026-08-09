"""Login da API local."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import current_user
from app.api.schemas import LoginIn, MessageOut, TokenOut
from app.security.authentication import AuthenticationError, SessionUser, token_store
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn) -> TokenOut:
    try:
        user = user_service.authenticate(payload.usuario, payload.senha)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
    return TokenOut(
        token=token_store.issue(user),
        usuario=user.usuario,
        nome=user.nome,
        papel=user.role.label,
    )


@router.get("/eu", response_model=TokenOut)
def me(user: SessionUser = Depends(current_user)) -> TokenOut:
    return TokenOut(token="", usuario=user.usuario, nome=user.nome, papel=user.role.label)


@router.post("/logout", response_model=MessageOut)
def logout(user: SessionUser = Depends(current_user)) -> MessageOut:
    return MessageOut(mensagem="Sessão encerrada neste dispositivo.")
