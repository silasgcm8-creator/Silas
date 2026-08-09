"""Registro do log de atividades."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.models.log import ActivityLog
from app.repositories.log_repository import LogRepository
from app.security.authentication import SessionUser


def record(
    session: Session,
    action: str,
    actor: SessionUser | None = None,
    detalhes: str | None = None,
    cliente_id: int | None = None,
    crediario_id: int | None = None,
    parcela_id: int | None = None,
) -> ActivityLog:
    entry = ActivityLog(
        usuario_id=actor.id if actor else None,
        usuario_nome=actor.nome if actor else "sistema",
        acao=action,
        detalhes=detalhes,
        cliente_id=cliente_id,
        crediario_id=crediario_id,
        parcela_id=parcela_id,
    )
    session.add(entry)
    return entry


def latest(session: Session, limit: int = 300, action: str | None = None) -> Sequence[ActivityLog]:
    return LogRepository(session).latest(limit=limit, action=action)
