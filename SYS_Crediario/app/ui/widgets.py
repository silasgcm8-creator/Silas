"""Componentes reutilizados por todas as telas."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui import icons
from app.ui.theme import ACCENT, TEXT, TEXT_MUTED, status_color
from app.utils.dates import format_br
from app.utils.money import format_brl

RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
CENTER = Qt.AlignmentFlag.AlignCenter
SORT_ROLE = Qt.ItemDataRole.UserRole + 1


class Card(QFrame):
    """Caixa com fundo, borda e cantos arredondados."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 10) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(18, 16, 18, 16)
        self.body.setSpacing(spacing)


class MetricCard(Card):
    """Indicador grande do painel."""

    def __init__(
        self,
        label: str,
        icon_name: str = "chart",
        color: str = ACCENT,
        hint: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, spacing=6)
        top = QHBoxLayout()
        top.setSpacing(8)

        badge = QLabel()
        badge.setPixmap(icons.pixmap(icon_name, color, 18))
        top.addWidget(badge)

        title = QLabel(label.upper())
        title.setObjectName("CardLabel")
        top.addWidget(title)
        top.addStretch(1)
        self.body.addLayout(top)

        self.value_label = QLabel("—")
        self.value_label.setObjectName("CardValue")
        self.body.addWidget(self.value_label)

        self.hint_label = QLabel(hint)
        self.hint_label.setObjectName("CardHint")
        self.body.addWidget(self.hint_label)

        self._color = color
        self.setMinimumHeight(112)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_value(self, value: str, hint: str = "", color: str | None = None) -> None:
        self.value_label.setText(value)
        self.value_label.setStyleSheet(f"color: {color or '#FFFFFF'};")
        if hint:
            self.hint_label.setText(hint)


class SectionTitle(QLabel):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("SectionTitle")


class SearchBox(QLineEdit):
    """Campo de busca com atraso: consulta somente quando o usuário para de digitar."""

    search = Signal(str)

    def __init__(self, placeholder: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self.addAction(icons.icon("search", TEXT_MUTED, 16), QLineEdit.ActionPosition.LeadingPosition)
        self.setMinimumHeight(38)
        self._timer_id = 0
        self.textChanged.connect(self._schedule)

    def _schedule(self, _text: str) -> None:
        if self._timer_id:
            self.killTimer(self._timer_id)
        self._timer_id = self.startTimer(280)

    def timerEvent(self, event) -> None:  # noqa: ANN001, N802
        if event.timerId() == self._timer_id:
            self.killTimer(self._timer_id)
            self._timer_id = 0
            self.search.emit(self.text().strip())


class DateEdit(QDateEdit):
    def __init__(self, value: date | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat("dd/MM/yyyy")
        self.setMinimumHeight(38)
        self.set_date(value or date.today())

    def set_date(self, value: date) -> None:
        self.setDate(QDate(value.year, value.month, value.day))

    def get_date(self) -> date:
        qdate = self.date()
        return date(qdate.year(), qdate.month(), qdate.day())


class DataTable(QTableWidget):
    """Tabela padronizada, somente leitura, com seleção por linha."""

    def __init__(
        self,
        headers: Sequence[str],
        stretch: int | None = 0,
        sortable: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(0, len(headers), parent)
        self.setHorizontalHeaderLabels(list(headers))
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(38)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSortingEnabled(sortable)

        header = self.horizontalHeader()
        header.setHighlightSections(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        if stretch is not None and 0 <= stretch < len(headers):
            header.setSectionResizeMode(stretch, QHeaderView.ResizeMode.Stretch)

    def fill(self, rows: Sequence[Sequence[QTableWidgetItem]]) -> None:
        """Substitui todo o conteúdo preservando a ordenação escolhida."""
        sorting = self.isSortingEnabled()
        self.setSortingEnabled(False)
        self.setRowCount(0)
        self.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, item in enumerate(row):
                self.setItem(r, c, item)
        self.setSortingEnabled(sorting)

    def selected_key(self, role: int = Qt.ItemDataRole.UserRole) -> int | None:
        row = self.currentRow()
        if row < 0:
            return None
        item = self.item(row, 0)
        if item is None:
            return None
        value = item.data(role)
        return int(value) if value is not None else None


class SortableItem(QTableWidgetItem):
    """Item que ordena pelo valor real (número/data), não pelo texto exibido."""

    def __lt__(self, other: QTableWidgetItem) -> bool:  # noqa: D105
        mine = self.data(SORT_ROLE)
        theirs = other.data(SORT_ROLE)
        if mine is None or theirs is None:
            return super().__lt__(other)
        try:
            return float(mine) < float(theirs)
        except (TypeError, ValueError):
            return str(mine) < str(theirs)


def text_item(value: object, key: int | None = None, bold: bool = False) -> QTableWidgetItem:
    item = SortableItem(str(value if value is not None else "—"))
    item.setData(SORT_ROLE, str(value).lower() if value is not None else "")
    if key is not None:
        item.setData(Qt.ItemDataRole.UserRole, int(key))
    if bold:
        font = QFont()
        font.setBold(True)
        item.setFont(font)
    return item


def money_item(
    value: Decimal, key: int | None = None, color: str | None = None, symbol: bool = True
) -> QTableWidgetItem:
    item = SortableItem(format_brl(value, symbol=symbol))
    item.setTextAlignment(RIGHT)
    item.setData(SORT_ROLE, float(value))
    if key is not None:
        item.setData(Qt.ItemDataRole.UserRole, int(key))
    if color:
        item.setForeground(QColor(color))
    return item


def date_item(value: date | None, key: int | None = None) -> QTableWidgetItem:
    item = SortableItem(format_br(value))
    item.setTextAlignment(CENTER)
    item.setData(SORT_ROLE, value.toordinal() if value else 0)
    if key is not None:
        item.setData(Qt.ItemDataRole.UserRole, int(key))
    return item


def number_item(value: int, key: int | None = None, color: str | None = None) -> QTableWidgetItem:
    item = SortableItem(str(value))
    item.setTextAlignment(CENTER)
    item.setData(SORT_ROLE, float(value))
    if key is not None:
        item.setData(Qt.ItemDataRole.UserRole, int(key))
    if color:
        item.setForeground(QColor(color))
    return item


def status_item(label: str, key: int | None = None) -> QTableWidgetItem:
    item = SortableItem(label)
    item.setTextAlignment(CENTER)
    item.setForeground(QColor(status_color(label)))
    item.setData(SORT_ROLE, label)
    font = QFont()
    font.setBold(True)
    item.setFont(font)
    if key is not None:
        item.setData(Qt.ItemDataRole.UserRole, int(key))
    return item


def primary_button(text: str, icon_name: str | None = None) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("Primary")
    button.setMinimumHeight(38)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if icon_name:
        button.setIcon(icons.icon(icon_name, "#FFFFFF", 16))
    return button


def button(text: str, icon_name: str | None = None, ghost: bool = False) -> QPushButton:
    widget = QPushButton(text)
    widget.setMinimumHeight(38)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if ghost:
        widget.setObjectName("Ghost")
    if icon_name:
        widget.setIcon(icons.icon(icon_name, TEXT, 16))
    return widget


def danger_button(text: str, icon_name: str | None = None) -> QPushButton:
    widget = QPushButton(text)
    widget.setObjectName("Danger")
    widget.setMinimumHeight(38)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if icon_name:
        widget.setIcon(icons.icon(icon_name, "#FFFFFF", 16))
    return widget


def field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("CardLabel")
    return label


def muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Muted")
    return label


def page_header(title: str, subtitle: str = "") -> QWidget:
    holder = QWidget()
    layout = QVBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    heading = QLabel(title)
    heading.setObjectName("PageTitle")
    layout.addWidget(heading)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setObjectName("PageSubtitle")
        layout.addWidget(sub)
    return holder


def info(parent: QWidget, title: str, message: str) -> None:
    QMessageBox.information(parent, title, message)


def warn(parent: QWidget, title: str, message: str) -> None:
    QMessageBox.warning(parent, title, message)


def error(parent: QWidget, title: str, message: str) -> None:
    QMessageBox.critical(parent, title, message)


def confirm(parent: QWidget, title: str, message: str) -> bool:
    answer = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes


def empty_hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Muted")
    label.setAlignment(CENTER)
    return label


__all__ = [
    "Card",
    "CENTER",
    "DataTable",
    "DateEdit",
    "MetricCard",
    "RIGHT",
    "SORT_ROLE",
    "SearchBox",
    "SectionTitle",
    "SortableItem",
    "TEXT",
    "button",
    "confirm",
    "danger_button",
    "date_item",
    "empty_hint",
    "error",
    "field_label",
    "info",
    "money_item",
    "muted",
    "number_item",
    "page_header",
    "primary_button",
    "status_item",
    "text_item",
    "warn",
]
