"""Clientes e ficha financeira via API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

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
    pagina: int = Query(1, ge=1, description="Página, começando em 1"),
    por_pagina: int = Query(
        client_service.PAGE_SIZE, ge=1, le=500, description="Itens por página"
    ),
    _: SessionUser = Depends(require_permission(Permission.CLIENT_VIEW)),
) -> list[ClientOut]:
    """Clientes ativos. O celular pagina para não baixar a base inteira."""
    rows = client_service.list_clients(
        busca, limit=por_pagina, offset=(pagina - 1) * por_pagina
    )
    return [ClientOut(**row.__dict__) for row in rows]


@router.get("/contagem/total", response_model=int)
def count_clients(
    busca: str = "",
    _: SessionUser = Depends(require_permission(Permission.CLIENT_VIEW)),
) -> int:
    """Quantos clientes atendem à busca — permite montar a paginação no celular."""
    return client_service.count_clients(busca)


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
