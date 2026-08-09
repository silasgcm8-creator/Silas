"""Classe base declarativa e mixins comuns."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarativa do SYS CREDIÁRIO."""


class TimestampMixin:
    criado_em: Mapped[datetime] = mapped_column(
        sa.DateTime, default=datetime.now, nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        sa.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )
