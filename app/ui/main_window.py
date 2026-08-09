"""Janela principal: menu lateral e navegação entre as telas."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_NAME, APP_VERSION
from app.security.authentication import SessionUser, current_session
from app.ui import icons
from app.ui.backup import BackupPage
from app.ui.clients import ClientsPage
from app.ui.context import AppContext
from app.ui.credits import CreditsPage
from app.ui.dashboard import DashboardPage
from app.ui.late import LatePage
from app.ui.payments import PaymentsPage
from app.ui.reports import ReportsPage
from app.ui.settings import SettingsPage
from app.ui.theme import ACCENT, TEXT_MUTED
from app.ui.widgets import button

MENU = [
    ("INÍCIO", "home"),
    ("CLIENTES", "users"),
    ("NOVO CREDIÁRIO", "plus"),
    ("CREDIÁRIOS", "list"),
    ("ATRASADOS", "alert"),
    ("RECEBIMENTOS", "cash"),
    ("RELATÓRIOS", "chart"),
    ("BACKUP", "shield"),
    ("CONFIGURAÇÕES", "gear"),
]

NEW_CREDIT_INDEX = 2


class MainWindow(QMainWindow):
    def __init__(self, user: SessionUser) -> None:
        super().__init__()
        self.ctx = AppContext(user)
        self.logged_out = False
        self.ctx.data_changed.connect(self._refresh_current)
        self.ctx.status_message.connect(self._show_status)

        self.setWindowTitle(f"{APP_NAME} — {user.nome}")
        self.setMinimumSize(1180, 720)
        self.resize(1360, 820)

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)

        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._sidebar())

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 22, 24, 18)
        content_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.dashboard_page = DashboardPage(self.ctx)
        self.clients_page = ClientsPage(self.ctx)
        self.credits_page = CreditsPage(self.ctx)
        self.late_page = LatePage(self.ctx)
        self.payments_page = PaymentsPage(self.ctx)
        self.reports_page = ReportsPage(self.ctx)
        self.backup_page = BackupPage(self.ctx)
        self.settings_page = SettingsPage(self.ctx)

        self.pages = {
            0: self.dashboard_page,
            1: self.clients_page,
            3: self.credits_page,
            4: self.late_page,
            5: self.payments_page,
            6: self.reports_page,
            7: self.backup_page,
            8: self.settings_page,
        }
        for page in (
            self.dashboard_page,
            self.clients_page,
            self.credits_page,
            self.late_page,
            self.payments_page,
            self.reports_page,
            self.backup_page,
            self.settings_page,
        ):
            self.stack.addWidget(page)

        content_layout.addWidget(self.stack)
        layout.addWidget(content, 1)

        status = QStatusBar()
        status.showMessage(f"{APP_NAME} {APP_VERSION} — pronto")
        self.setStatusBar(status)

        self.nav.setCurrentRow(0)
        self._navigate(0)

    def _sidebar(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("Sidebar")
        panel.setFixedWidth(232)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 22, 16, 18)
        layout.setSpacing(14)

        brand_row = QHBoxLayout()
        mark = QLabel()
        mark.setPixmap(icons.pixmap("shield", ACCENT, 26))
        brand_row.addWidget(mark)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        name = QLabel("SYS")
        name.setObjectName("Brand")
        sub = QLabel("CREDIÁRIO")
        sub.setObjectName("BrandSub")
        brand_text.addWidget(name)
        brand_text.addWidget(sub)
        brand_row.addLayout(brand_text)
        brand_row.addStretch(1)
        layout.addLayout(brand_row)

        self.nav = QListWidget()
        self.nav.setObjectName("Nav")
        self.nav.setIconSize(QSize(18, 18))
        self.nav.setFrameShape(QFrame.Shape.NoFrame)
        self.nav.setCursor(Qt.CursorShape.PointingHandCursor)
        for label, icon_name in MENU:
            item = QListWidgetItem(icons.icon(icon_name, TEXT_MUTED, 18), label)
            self.nav.addItem(item)
        self.nav.currentRowChanged.connect(self._navigate)
        layout.addWidget(self.nav, 1)

        user_box = QVBoxLayout()
        user_box.setSpacing(2)
        who = QLabel(self.ctx.user.nome)
        who.setStyleSheet("font-weight: 600;")
        role = QLabel(self.ctx.user.role.label)
        role.setObjectName("Muted")
        user_box.addWidget(who)
        user_box.addWidget(role)
        layout.addLayout(user_box)

        logout = button("Sair do sistema", "logout", ghost=True)
        logout.clicked.connect(self._logout)
        layout.addWidget(logout)
        return panel

    def _navigate(self, index: int) -> None:
        if index == NEW_CREDIT_INDEX:
            self.nav.blockSignals(True)
            self.nav.setCurrentRow(3)
            self.nav.blockSignals(False)
            self.stack.setCurrentWidget(self.credits_page)
            self.credits_page.refresh()
            self.credits_page.new_credit()
            return

        page = self.pages.get(index)
        if page is None:
            return
        self.stack.setCurrentWidget(page)
        page.refresh()

    def _refresh_current(self) -> None:
        page = self.stack.currentWidget()
        refresh = getattr(page, "refresh", None)
        if callable(refresh):
            refresh()

    def _show_status(self, message: str) -> None:
        self.statusBar().showMessage(message, 6000)

    def _logout(self) -> None:
        self.logged_out = True
        current_session.logout()
        self.close()

    def closeEvent(self, event) -> None:  # noqa: ANN001, N802
        from app.api.server import api_server

        if api_server.is_running:
            api_server.stop()
        super().closeEvent(event)
