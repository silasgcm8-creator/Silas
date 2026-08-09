"""Exportação de relatórios.

A versão 1 entrega CSV nativo. PDF e Excel já possuem ponto de extensão
registrado: basta instalar a biblioteca e registrar o exportador.
"""

from __future__ import annotations

import csv
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

Row = Sequence[object]
Exporter = Callable[[Path, Sequence[str], Iterable[Row]], Path]

_EXPORTERS: dict[str, Exporter] = {}


def register_exporter(fmt: str, exporter: Exporter) -> None:
    _EXPORTERS[fmt.lower()] = exporter


def available_formats() -> list[str]:
    return sorted(_EXPORTERS)


def export(fmt: str, path: Path, headers: Sequence[str], rows: Iterable[Row]) -> Path:
    key = fmt.lower()
    if key not in _EXPORTERS:
        raise ValueError(
            f"Formato '{fmt}' indisponível. Formatos ativos: {', '.join(available_formats())}."
        )
    return _EXPORTERS[key](Path(path), headers, rows)


def export_csv(path: Path, headers: Sequence[str], rows: Iterable[Row]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(headers)
        for row in rows:
            writer.writerow(list(row))
    return path


register_exporter("csv", export_csv)


def _export_xlsx(path: Path, headers: Sequence[str], rows: Iterable[Row]) -> Path:
    from openpyxl import Workbook  # type: ignore import-not-found

    book = Workbook()
    sheet = book.active
    sheet.append(list(headers))
    for row in rows:
        sheet.append(list(row))
    book.save(path)
    return Path(path)


def _export_pdf(path: Path, headers: Sequence[str], rows: Iterable[Row]) -> Path:
    from reportlab.lib.pagesizes import A4  # type: ignore import-not-found
    from reportlab.platypus import SimpleDocTemplate, Table  # type: ignore

    document = SimpleDocTemplate(str(path), pagesize=A4)
    document.build([Table([list(headers)] + [list(r) for r in rows])])
    return Path(path)


def enable_optional_exporters() -> None:
    """Ativa XLSX/PDF quando as bibliotecas opcionais estiverem instaladas."""
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        pass
    else:
        register_exporter("xlsx", _export_xlsx)

    try:
        import reportlab  # noqa: F401
    except ImportError:
        pass
    else:
        register_exporter("pdf", _export_pdf)


enable_optional_exporters()
