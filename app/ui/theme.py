"""Identidade visual do SYS CREDIÁRIO.

Paleta corporativa: azul profundo e roxo como base, branco e cinza para o
conteúdo, e as três cores de situação (verde, amarelo, vermelho).
"""

from __future__ import annotations

BACKGROUND = "#0B1020"
SIDEBAR = "#0E1631"
SURFACE = "#141C36"
SURFACE_ALT = "#1A2445"
BORDER = "#232F55"
TEXT = "#EAEEF9"
TEXT_MUTED = "#93A0C0"
ACCENT = "#6366F1"
ACCENT_HOVER = "#7C7EF5"
ACCENT_PRESSED = "#4F46E5"
PURPLE = "#8B5CF6"
GREEN = "#22C55E"
YELLOW = "#F5A524"
RED = "#EF4444"
SOFT_BLACK = "#080C18"

FONT_FAMILY = "Segoe UI, Inter, Noto Sans, Arial"

STATUS_COLORS = {
    "PAGO": GREEN,
    "EM ABERTO": YELLOW,
    "ATRASADO": RED,
}


def status_color(status: str) -> str:
    return STATUS_COLORS.get((status or "").upper().split(" —")[0], TEXT_MUTED)


STYLESHEET = f"""
* {{
    font-family: {FONT_FAMILY};
    font-size: 13px;
    color: {TEXT};
    outline: none;
}}

QWidget#Root, QDialog, QMainWindow {{
    background-color: {BACKGROUND};
}}

QWidget#Sidebar {{
    background-color: {SIDEBAR};
    border-right: 1px solid {BORDER};
}}

QLabel#Brand {{
    font-size: 17px;
    font-weight: 700;
    letter-spacing: 1px;
    color: #FFFFFF;
}}

QLabel#BrandSub {{
    font-size: 11px;
    color: {TEXT_MUTED};
    letter-spacing: 2px;
}}

QListWidget#Nav {{
    background: transparent;
    border: none;
    padding: 8px 10px;
}}

QListWidget#Nav::item {{
    height: 42px;
    padding-left: 12px;
    border-radius: 10px;
    color: {TEXT_MUTED};
}}

QListWidget#Nav::item:hover {{
    background-color: {SURFACE};
    color: {TEXT};
}}

QListWidget#Nav::item:selected {{
    background-color: {ACCENT};
    color: #FFFFFF;
    font-weight: 600;
}}

QLabel#PageTitle {{
    font-size: 22px;
    font-weight: 700;
    color: #FFFFFF;
}}

QLabel#PageSubtitle {{
    font-size: 12px;
    color: {TEXT_MUTED};
}}

QLabel#SectionTitle {{
    font-size: 14px;
    font-weight: 600;
    color: #FFFFFF;
}}

QFrame#Card, QWidget#Card {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}

QLabel#CardLabel {{
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    color: {TEXT_MUTED};
}}

QLabel#CardValue {{
    font-size: 22px;
    font-weight: 700;
    color: #FFFFFF;
}}

QLabel#CardHint {{
    font-size: 11px;
    color: {TEXT_MUTED};
}}

QLabel#Muted {{
    color: {TEXT_MUTED};
}}

QLineEdit, QComboBox, QDateEdit, QSpinBox, QPlainTextEdit, QTextEdit {{
    background-color: {SURFACE_ALT};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 9px 12px;
    selection-background-color: {ACCENT};
}}

QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus {{
    border: 1px solid {ACCENT};
}}

QComboBox::drop-down, QDateEdit::drop-down {{
    border: none;
    width: 22px;
}}

QComboBox QAbstractItemView {{
    background-color: {SURFACE_ALT};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    padding: 4px;
}}

QPushButton {{
    background-color: {SURFACE_ALT};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 9px 16px;
    color: {TEXT};
}}

QPushButton:hover {{
    background-color: {BORDER};
}}

QPushButton:disabled {{
    color: #5A688C;
}}

QPushButton#Primary {{
    background-color: {ACCENT};
    border: 1px solid {ACCENT};
    color: #FFFFFF;
    font-weight: 600;
}}

QPushButton#Primary:hover {{
    background-color: {ACCENT_HOVER};
}}

QPushButton#Primary:pressed {{
    background-color: {ACCENT_PRESSED};
}}

QPushButton#Danger {{
    background-color: {RED};
    border: 1px solid {RED};
    color: #FFFFFF;
    font-weight: 600;
}}

QPushButton#Ghost {{
    background: transparent;
    border: 1px solid {BORDER};
    color: {TEXT_MUTED};
}}

QPushButton#Ghost:hover {{
    color: {TEXT};
    border-color: {ACCENT};
}}

QTableWidget, QTableView {{
    background-color: {SURFACE};
    alternate-background-color: {SURFACE_ALT};
    border: 1px solid {BORDER};
    border-radius: 12px;
    gridline-color: transparent;
    selection-background-color: {ACCENT};
    selection-color: #FFFFFF;
}}

QTableWidget::item, QTableView::item {{
    padding: 8px 10px;
    border: none;
}}

QHeaderView::section {{
    background-color: {SURFACE};
    color: {TEXT_MUTED};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 10px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
}}

QTableCornerButton::section {{
    background-color: {SURFACE};
    border: none;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 4px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: {ACCENT};
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0px;
    width: 0px;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 4px;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 5px;
    min-width: 30px;
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 12px;
    top: -1px;
}}

QTabBar::tab {{
    background: transparent;
    color: {TEXT_MUTED};
    padding: 10px 18px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
}}

QTabBar::tab:selected {{
    background: {SURFACE};
    color: #FFFFFF;
    font-weight: 600;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {BORDER};
    background: {SURFACE_ALT};
}}

QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

QMessageBox {{
    background-color: {SURFACE};
}}

QToolTip {{
    background-color: {SOFT_BLACK};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 6px;
    border-radius: 6px;
}}

QStatusBar {{
    background: {SIDEBAR};
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER};
}}
"""
