"""Consultas de usuários."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from app.models.status import Role
from app.models.user import User
from app.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def get_by_username(self, username: str) -> User | None:
        stmt = sa.select(User).where(User.usuario == (username or "").strip().lower())
        return self.session.scalars(stmt).first()

    def list_active(self) -> Sequence[User]:
        stmt = sa.select(User).order_by(User.nome)
        return self.session.scalars(stmt).all()

    def has_admin(self) -> bool:
        stmt = (
            sa.select(sa.func.count())
            .select_from(User)
            .where(User.papel == Role.ADMIN.value, User.ativo.is_(True))
        )
        return int(self.session.scalar(stmt) or 0) > 0
