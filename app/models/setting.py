"""Configurações persistentes (chave/valor)."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Setting(Base):
    __tablename__ = "configuracoes"

    chave: Mapped[str] = mapped_column(sa.String(60), primary_key=True)
    valor: Mapped[str] = mapped_column(sa.String(255), default="")
    atualizado_em: Mapped[datetime] = mapped_column(
        sa.DateTime, default=datetime.now, onupdate=datetime.now
    )
