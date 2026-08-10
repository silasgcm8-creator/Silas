"""Janela principal: menu lateral e navegação entre as telas."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QKeySequence
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
from app.security.permissions import Permission
from app.ui import icons
from app.ui.backup import BackupPage
from app.ui.charges import ChargesPage
from app.ui.clients import ClientsPage
from app.ui.context import AppContext
from app.ui.credits import CreditsPage
from app.ui.dashboard import DashboardPage
from app.ui.issue_charge import IssueChargePage
from app.ui.late import LatePage
from app.ui.payments import PaymentsPage
from app.ui.receive_payment import ReceivePaymentPage
from app.ui.reports import ReportsPage
from app.ui.settings import SettingsPage
from app.ui.staff_home import StaffHomePage
from app.ui.theme import ACCENT, TEXT_MUTED
from app.ui.widgets import button

#: Rótulo, ícone e permissão exigida. Sem a permissão o item nem aparece — o
#: funcionário não vê a estrutura administrativa, e as regras continuam sendo
#: conferidas nos serviços, não só aqui.
MENU: list[tuple[str, str, Permission | None]] = [
    ("INÍCIO", "home", None),
    ("CLIENTES", "users", Permission.CLIENT_VIEW),
    ("NOVO CREDIÁRIO", "plus", Permission.CREDIT_CREATE),
    ("CREDIÁRIOS", "list", Permission.CREDIT_VIEW),
    ("REGISTRAR PAGAMENTO", "cash", Permission.PAYMENT_REGISTER),
    ("GERAR BOLETO", "receipt", Permission.CHARGE_ISSUE),
    ("BOLETOS", "list", Permission.CHARGE_VIEW),
    ("ATRASADOS", "alert", Permission.FINANCE_OVERVIEW),
    ("RECEBIMENTOS", "cash", Permission.PAYMENT_REGISTER),
    ("RELATÓRIOS", "chart", Permission.FINANCE_OVERVIEW),
    ("BACKUP", "shield", Permission.BACKUP_RESTORE),
    ("CONFIGURAÇÕES", "gear", Permission.SETTINGS),
]


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

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 22, 24, 18)
        content_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.clients_page = ClientsPage(self.ctx)
        self.credits_page = CreditsPage(self.ctx)
        self.payments_page = PaymentsPage(self.ctx)

        # O administrador começa no painel; o funcionário, no terminal simples.
        self.is_admin_view = self.ctx.can(Permission.FINANCE_OVERVIEW)
        if self.is_admin_view:
            self.home_page: QWidget = DashboardPage(self.ctx)
        else:
            home = StaffHomePage(self.ctx)
            home.new_client.connect(self._staff_new_client)
            home.search_client.connect(self._staff_search_client)
            home.register_payment.connect(self._staff_register_payment)
            home.issue_charge.connect(self._staff_issue_charge)
            home.open_client.connect(self._staff_open_client)
            self.home_page = home

        self.pages: dict[str, QWidget] = {"INÍCIO": self.home_page}
        if self.ctx.can(Permission.CLIENT_VIEW):
            self.pages["CLIENTES"] = self.clients_page
        if self.ctx.can(Permission.CREDIT_VIEW):
            self.pages["CREDIÁRIOS"] = self.credits_page
        if self.ctx.can(Permission.PAYMENT_REGISTER):
            self.pages["REGISTRAR PAGAMENTO"] = ReceivePaymentPage(self.ctx)
        if self.ctx.can(Permission.CHARGE_ISSUE):
            self.pages["GERAR BOLETO"] = IssueChargePage(self.ctx)
        if self.ctx.can(Permission.CHARGE_VIEW):
            self.pages["BOLETOS"] = ChargesPage(self.ctx)
        if self.ctx.can(Permission.PAYMENT_REGISTER):
            self.pages["RECEBIMENTOS"] = self.payments_page
        if self.ctx.can(Permission.FINANCE_OVERVIEW):
            self.pages["ATRASADOS"] = LatePage(self.ctx)
            self.pages["RELATÓRIOS"] = ReportsPage(self.ctx)
        if self.ctx.can(Permission.BACKUP_RESTORE):
            self.pages["BACKUP"] = BackupPage(self.ctx)
        if self.ctx.can(Permission.SETTINGS):
            self.pages["CONFIGURAÇÕES"] = SettingsPage(self.ctx)

        for page in dict.fromkeys(self.pages.values()):
            self.stack.addWidget(page)

        content_layout.addWidget(self.stack)
        # A barra lateral é montada depois das páginas: ela só mostra os itens
        # que existem para este perfil.
        layout.addWidget(self._sidebar())
        layout.addWidget(content, 1)

        status = QStatusBar()
        status.showMessage(f"{APP_NAME} {APP_VERSION} — pronto")
        self.setStatusBar(status)

        self._install_shortcuts()
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
        self.menu_labels: list[str] = []
        for label, icon_name, permissao in MENU:
            if label != "NOVO CREDIÁRIO" and label not in self.pages:
                continue
            if permissao is not None and not self.ctx.can(permissao):
                continue
            self.nav.addItem(QListWidgetItem(icons.icon(icon_name, TEXT_MUTED, 18), label))
            self.menu_labels.append(label)
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

    def _install_shortcuts(self) -> None:
        """Atalhos do balcão. Só disparam quando a ação é permitida."""
        atalhos = (
            ("Ctrl+F", self._staff_search_client, Permission.CLIENT_VIEW),
            ("Ctrl+N", self._staff_new_client, Permission.CLIENT_CREATE),
            ("Ctrl+R", self._staff_register_payment, Permission.PAYMENT_REGISTER),
            ("Ctrl+B", self._staff_issue_charge, Permission.CHARGE_ISSUE),
        )
        for sequencia, alvo, permissao in atalhos:
            if not self.ctx.can(permissao):
                continue
            acao = QAction(self)
            acao.setShortcut(QKeySequence(sequencia))
            acao.triggered.connect(alvo)
            self.addAction(acao)

    def _go(self, label: str) -> QWidget | None:
        """Leva o menu e a pilha para a tela indicada pelo rótulo."""
        page = self.pages.get(label)
        if page is None:
            return None
        if label in self.menu_labels:
            self.nav.blockSignals(True)
            self.nav.setCurrentRow(self.menu_labels.index(label))
            self.nav.blockSignals(False)
        self.stack.setCurrentWidget(page)
        page.refresh()
        return page

    def _staff_new_client(self) -> None:
        page = self._go("CLIENTES")
        if page is not None:
            page.new_client()

    def _staff_search_client(self) -> None:
        page = self._go("CLIENTES")
        if page is not None:
            page.focus_search()

    def _staff_register_payment(self) -> None:
        """Vai direto para a tela de recebimento, com a busca em foco."""
        page = self._go("REGISTRAR PAGAMENTO")
        if page is not None:
            page.search.setFocus()

    def _staff_issue_charge(self) -> None:
        """Vai direto para a tela operacional de emissão, com a busca em foco."""
        page = self._go("GERAR BOLETO")
        if page is not None:
            page.search.setFocus()

    def _staff_open_client(self, client_id: int) -> None:
        """Abre a ficha de um cadastro recente, sem passar pela busca."""
        page = self._go("CLIENTES")
        if page is not None:
            page.open_client(client_id)

    def _navigate(self, index: int) -> None:
        if not 0 <= index < len(self.menu_labels):
            return
        label = self.menu_labels[index]

        if label == "NOVO CREDIÁRIO":
            page = self._go("CREDIÁRIOS")
            if page is not None:
                page.new_credit()
            return

        self._go(label)

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
