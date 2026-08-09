"""Usuários do sistema."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.status import Role


class User(Base, TimestampMixin):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario: Mapped[str] = mapped_column(sa.String(32), unique=True, index=True)
    nome: Mapped[str] = mapped_column(sa.String(120))
    senha_hash: Mapped[str] = mapped_column(sa.String(255))
    papel: Mapped[str] = mapped_column(sa.String(20), default=Role.STAFF.value)
    ativo: Mapped[bool] = mapped_column(sa.Boolean, default=True)
    ultimo_acesso: Mapped[datetime | None] = mapped_column(sa.DateTime, nullable=True)

    @property
    def role(self) -> Role:
        return Role.from_value(self.papel)

    @property
    def is_admin(self) -> bool:
        return self.role is Role.ADMIN

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.usuario} ({self.papel})>"
