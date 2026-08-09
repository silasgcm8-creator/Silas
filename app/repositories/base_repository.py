"""Repositório genérico com as operações comuns a todos os modelos."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Generic, TypeVar

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, entity_id: int) -> ModelT | None:
        return self.session.get(self.model, entity_id)

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        self.session.flush()
        return entity

    def delete(self, entity: ModelT) -> None:
        self.session.delete(entity)
        self.session.flush()

    def list_all(self, order_by=None) -> Sequence[ModelT]:  # noqa: ANN001
        stmt = sa.select(self.model)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        return self.session.scalars(stmt).all()

    def count(self) -> int:
        return int(
            self.session.scalar(sa.select(sa.func.count()).select_from(self.model)) or 0
        )
