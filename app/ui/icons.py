"""Ícones vetoriais desenhados em SVG embutido (sem arquivos externos)."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from app.ui.theme import TEXT

_PATHS: dict[str, str] = {
    "home": "M3 11.5 12 4l9 7.5M5.5 10v9.5h13V10M9.75 19.5V14h4.5v5.5",
    "users": (
        "M8.5 11a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z"
        "M2.8 19.4c0-3.1 2.6-5.2 5.7-5.2s5.7 2.1 5.7 5.2"
        "M16.2 5.2a3 3 0 0 1 0 5.8M17 14.4c2.5.4 4.2 2.2 4.2 5"
    ),
    "plus": "M12 5v14M5 12h14",
    "list": "M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01",
    "alert": "M12 4 2.8 20h18.4L12 4ZM12 10v4.5M12 17.6h.01",
    "cash": (
        "M3 6.5h18v11H3zM12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z"
        "M6.4 10.2h.01M17.6 13.8h.01"
    ),
    "chart": "M4 20V10M10 20V4M16 20v-7M22 20H2",
    "shield": "M12 3.2 4.8 6v6c0 4.3 3 7.6 7.2 8.8 4.2-1.2 7.2-4.5 7.2-8.8V6L12 3.2Z",
    "gear": (
        "M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z"
        "M19.4 12a7.6 7.6 0 0 0-.1-1.2l2-1.5-2-3.4-2.3.9a7.4 7.4 0 0 0-2-1.2L14.6 3H9.4"
        "L9 5.6a7.4 7.4 0 0 0-2 1.2l-2.3-.9-2 3.4 2 1.5a7.6 7.6 0 0 0 0 2.4l-2 1.5 2 3.4"
        "2.3-.9c.6.5 1.3.9 2 1.2l.4 2.6h5.2l.4-2.6c.7-.3 1.4-.7 2-1.2l2.3.9 2-3.4-2-1.5"
        "c.1-.4.1-.8.1-1.2Z"
    ),
    "logout": "M14.5 16.5 19 12l-4.5-4.5M19 12H8M11 4.5H5.5v15H11",
    "search": "M11 18.2a7.2 7.2 0 1 0 0-14.4 7.2 7.2 0 0 0 0 14.4ZM20.5 20.5l-4.2-4.2",
    "whatsapp": (
        "M12 3.6a8.4 8.4 0 0 0-7.2 12.7L3.6 20.4l4.3-1.1A8.4 8.4 0 1 0 12 3.6Z"
        "M9.2 8.6c.3 1.7 1.4 3 2.9 3.8l1-1.1 2 .9-.2 1.6c-2.6.3-5.3-1.9-6.2-4.6l1.5-.6Z"
    ),
    "download": "M12 4v10.5M7.5 10.5 12 15l4.5-4.5M4.5 19.5h15",
    "upload": "M12 15.5V5M7.5 9 12 4.5 16.5 9M4.5 19.5h15",
    "check": "M4.5 12.5 9.5 17.5 19.5 6.5",
    "undo": "M4 10h9.5a5 5 0 1 1 0 10H8M4 10l4-4M4 10l4 4",
    "user-plus": (
        "M9.5 11.5a3.4 3.4 0 1 0 0-6.8 3.4 3.4 0 0 0 0 6.8"
        "M3.2 19.6c0-3.2 2.8-5.4 6.3-5.4 1.4 0 2.7.4 3.7 1M18 13.5v5M15.5 16h5"
    ),
    "phone": (
        "M6.2 3.8h3.1l1.6 4-2 1.4a11 11 0 0 0 5.9 5.9l1.4-2 4 1.6v3.1"
        "c0 .9-.7 1.6-1.6 1.6A16.8 16.8 0 0 1 4.6 5.4c0-.9.7-1.6 1.6-1.6Z"
    ),
    "wifi": (
        "M4 9.5a12 12 0 0 1 16 0M7 13a8 8 0 0 1 10 0M10 16.4a3.5 3.5 0 0 1 4 0"
        "M12 19.6h.01"
    ),
}


def svg(name: str, color: str = TEXT, width: float = 1.7) -> str:
    path = _PATHS.get(name, _PATHS["list"])
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{width}" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )


def pixmap(name: str, color: str = TEXT, size: int = 20) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg(name, color).encode()))
    image = QPixmap(QSize(size, size))
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return image


def icon(name: str, color: str = TEXT, size: int = 20) -> QIcon:
    return QIcon(pixmap(name, color, size))
