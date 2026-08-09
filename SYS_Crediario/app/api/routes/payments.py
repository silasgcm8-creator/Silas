"""Registro de pagamento via API (usuários autorizados)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import require_permission
from app.api.schemas import MessageOut, PaymentIn
from app.security.authentication import SessionUser
from app.security.permissions import Permission
from app.services import payment_service
from app.services.errors import BusinessError, NotFoundError

router = APIRouter(prefix="/pagamentos", tags=["Pagamentos"])


@router.post("", response_model=MessageOut)
def register_payment(
    payload: PaymentIn,
    user: SessionUser = Depends(require_permission(Permission.PAYMENT_REGISTER)),
) -> MessageOut:
    try:
        payment_service.mark_as_paid(payload.parcela_id, user, payload.data_pagamento)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except BusinessError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return MessageOut(mensagem="Pagamento registrado.")
