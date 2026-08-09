"""Clientes e ficha financeira via API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import require_permission
from app.api.schemas import ClientOut, ClientSummaryOut
from app.security.authentication import SessionUser
from app.security.permissions import Permission
from app.services import client_service
from app.services.errors import NotFoundError

router = APIRouter(prefix="/clientes", tags=["Clientes"])


@router.get("", response_model=list[ClientOut])
def list_clients(
    busca: str = "",
    _: SessionUser = Depends(require_permission(Permission.CLIENT_VIEW)),
) -> list[ClientOut]:
    return [ClientOut(**row.__dict__) for row in client_service.list_clients(busca)]


@router.get("/{client_id}", response_model=ClientSummaryOut)
def client_summary(
    client_id: int,
    _: SessionUser = Depends(require_permission(Permission.CLIENT_VIEW)),
) -> ClientSummaryOut:
    try:
        summary = client_service.get_summary(client_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ClientSummaryOut(**summary.__dict__)
