"""Tipos de coluna personalizados."""

from __future__ import annotations

from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.types import TypeDecorator

from app.utils.money import from_cents, to_cents


class MoneyType(TypeDecorator):
    """Dinheiro persistido como centavos inteiros.

    Evita completamente os erros de arredondamento do ponto flutuante e mantém
    o comportamento idêntico em SQLite e PostgreSQL.
    """

    impl = sa.Integer
    cache_ok = True

    def process_bind_param(self, value, dialect):  # noqa: ANN001
        if value is None:
            return None
        return to_cents(value)

    def process_result_value(self, value, dialect) -> Decimal | None:  # noqa: ANN001
        if value is None:
            return None
        return from_cents(int(value))


def sum_cents(column) -> sa.ColumnElement[int]:  # noqa: ANN001
    """SUM de uma coluna monetária devolvendo centavos inteiros.

    O CAST explícito garante um int previsível, sem depender da propagação de
    tipos das funções de agregação.
    """
    return sa.func.coalesce(sa.func.sum(sa.cast(column, sa.Integer)), 0)
