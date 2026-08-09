"""Clientes — apenas nome, CPF e telefone (princípio da minimização, LGPD)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.credit import Credit


class Client(Base, TimestampMixin):
    __tablename__ = "clientes"
    __table_args__ = (sa.Index("ix_clientes_nome_cpf", "nome", "cpf"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(sa.String(120), index=True)
    cpf: Mapped[str] = mapped_column(sa.String(14), unique=True, index=True)
    telefone: Mapped[str] = mapped_column(sa.String(20), index=True)

    credits: Mapped[list["Credit"]] = relationship(
        back_populates="client", cascade="all, delete-orphan", passive_deletes=False
    )

    @property
    def primeiro_nome(self) -> str:
        return self.nome.split(" ")[0]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Client {self.nome} {self.cpf}>"
