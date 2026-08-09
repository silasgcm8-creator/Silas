"""Login da API local."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import bearer_token, current_user
from app.api.schemas import IdentityOut, LoginIn, MessageOut, TokenOut
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


@router.get("/eu", response_model=IdentityOut)
def me(user: SessionUser = Depends(current_user)) -> IdentityOut:
    return IdentityOut(usuario=user.usuario, nome=user.nome, papel=user.role.label)


@router.post("/logout", response_model=MessageOut)
def logout(
    token: str = Depends(bearer_token),
    user: SessionUser = Depends(current_user),  # noqa: ARG001 - exige token válido
) -> MessageOut:
    """Invalida o token de verdade: um celular perdido perde o acesso na hora."""
    token_store.revoke(token)
    return MessageOut(mensagem="Sessão encerrada neste dispositivo.")
