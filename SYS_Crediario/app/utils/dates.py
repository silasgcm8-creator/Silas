"""Datas, vencimentos e períodos usados nos relatórios."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

ISO = "%Y-%m-%d"
BR = "%d/%m/%Y"


def today() -> date:
    return date.today()


def add_months(reference: date, months: int) -> date:
    """Soma meses preservando o dia sempre que o mês destino permitir."""
    total = reference.month - 1 + months
    year = reference.year + total // 12
    month = total % 12 + 1
    day = min(reference.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def parse_iso(value: str) -> date:
    return datetime.strptime(value.strip(), ISO).date()


def parse_br(value: str) -> date:
    return datetime.strptime(value.strip(), BR).date()


def parse_any(value: str) -> date:
    text = (value or "").strip()
    for parser in (parse_br, parse_iso):
        try:
            return parser(text)
        except ValueError:
            continue
    raise ValueError("Data inválida. Use o formato DD/MM/AAAA.")


def format_br(value: date | datetime | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        value = value.date()
    return value.strftime(BR)


def format_datetime_br(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%d/%m/%Y %H:%M")


def days_late(due: date, reference: date | None = None) -> int:
    reference = reference or today()
    return max(0, (reference - due).days)


def month_bounds(reference: date | None = None) -> tuple[date, date]:
    reference = reference or today()
    first = reference.replace(day=1)
    last = reference.replace(day=calendar.monthrange(reference.year, reference.month)[1])
    return first, last


def week_bounds(reference: date | None = None) -> tuple[date, date]:
    reference = reference or today()
    start = reference - timedelta(days=reference.weekday())
    return start, start + timedelta(days=6)


def period_bounds(name: str, reference: date | None = None) -> tuple[date, date]:
    """Períodos prontos usados nas telas de recebimentos e relatórios."""
    reference = reference or today()
    key = (name or "").strip().lower()
    if key == "hoje":
        return reference, reference
    if key in {"semana", "esta semana"}:
        return week_bounds(reference)
    if key in {"mes", "mês", "este mes", "este mês"}:
        return month_bounds(reference)
    if key in {"ano", "este ano"}:
        return date(reference.year, 1, 1), date(reference.year, 12, 31)
    raise ValueError(f"Período desconhecido: {name!r}")


def timestamp_tag(moment: datetime | None = None) -> str:
    """Sufixo usado no nome dos backups: 2026-08-08_2030."""
    moment = moment or datetime.now()
    return moment.strftime("%Y-%m-%d_%H%M")
