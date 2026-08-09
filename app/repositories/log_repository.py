"""Consultas do log de atividades."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from app.models.log import ActivityLog
from app.repositories.base_repository import BaseRepository


class LogRepository(BaseRepository[ActivityLog]):
    model = ActivityLog

    def latest(self, limit: int = 300, action: str | None = None) -> Sequence[ActivityLog]:
        stmt = sa.select(ActivityLog).order_by(ActivityLog.criado_em.desc()).limit(limit)
        if action:
            stmt = stmt.where(ActivityLog.acao == action)
        return self.session.scalars(stmt).all()
