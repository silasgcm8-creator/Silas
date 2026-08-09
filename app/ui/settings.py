"""Configurações: usuários, acesso pelo celular e log de atividades."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.api.server import api_server
from app.config import APP_NAME, APP_VERSION
from app.models.status import Role
from app.security.password import algorithm
from app.security.permissions import Permission, PermissionDenied
from app.services import log_service, user_service
from app.services.errors import BusinessError, ValidationError
from app.ui.context import AppContext
from app.ui.theme import GREEN, RED, TEXT_MUTED
from app.ui.widgets import (
    Card,
    DataTable,
    SectionTitle,
    button,
    danger_button,
    error,
    field_label,
    info,
    page_header,
    primary_button,
    text_item,
    warn,
)
from app.utils.dates import format_datetime_br
from app.database.connection import session_scope


class UserDialog(QDialog):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Novo usuário")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)
        layout.addWidget(page_header("Novo usuário", "Defina o papel de acesso"))

        card = Card()
        form = QFormLayout()
        form.setSpacing(10)
        self.name_edit = QLineEdit()
        self.user_edit = QLineEdit()
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.role_combo = QComboBox()
        self.role_combo.setMinimumHeight(38)
        for role in (Role.STAFF, Role.ADMIN):
            self.role_combo.addItem(role.label, role.value)

        form.addRow(field_label("NOME"), self.name_edit)
        form.addRow(field_label("USUÁRIO"), self.user_edit)
        form.addRow(field_label("SENHA"), self.pass_edit)
        form.addRow(field_label("PAPEL"), self.role_combo)
        card.body.addLayout(form)
        layout.addWidget(card)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel = button("Cancelar", ghost=True)
        cancel.clicked.connect(self.reject)
        save = primary_button("Criar usuário", "user-plus")
        save.clicked.connect(self._save)
        actions.addWidget(cancel)
        actions.addWidget(save)
        layout.addLayout(actions)

    def _save(self) -> None:
        try:
            user_service.create_user(
                self.name_edit.text(),
                self.user_edit.text(),
                self.pass_edit.text(),
                Role.from_value(str(self.role_combo.currentData())),
                self.ctx.user,
            )
        except (ValidationError, BusinessError, PermissionDenied) as exc:
            warn(self, "Usuário", str(exc))
            return
        self.accept()


class PasswordDialog(QDialog):
    def __init__(self, ctx: AppContext, user_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.user_id = user_id
        self.setWindowTitle("Alterar senha")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        layout.addWidget(page_header("Alterar senha", "Mínimo de 6 caracteres"))

        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_edit = QLineEdit()
        self.confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)

        card = Card()
        form = QFormLayout()
        form.addRow(field_label("NOVA SENHA"), self.pass_edit)
        form.addRow(field_label("CONFIRMAR"), self.confirm_edit)
        card.body.addLayout(form)
        layout.addWidget(card)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel = button("Cancelar", ghost=True)
        cancel.clicked.connect(self.reject)
        save = primary_button("Salvar senha", "check")
        save.clicked.connect(self._save)
        actions.addWidget(cancel)
        actions.addWidget(save)
        layout.addLayout(actions)

    def _save(self) -> None:
        if self.pass_edit.text() != self.confirm_edit.text():
            warn(self, "Senha", "As senhas digitadas não conferem.")
            return
        try:
            user_service.change_password(self.user_id, self.pass_edit.text(), self.ctx.user)
        except (ValidationError, BusinessError, PermissionDenied) as exc:
            warn(self, "Senha", str(exc))
            return
        self.accept()


class SettingsPage(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(page_header("Configurações", "Usuários, acesso móvel e auditoria"))

        self.tabs = QTabWidget()
        self.tabs.addTab(self._users_tab(), "Usuários")
        self.tabs.addTab(self._mobile_tab(), "Acesso pelo celular")
        self.tabs.addTab(self._logs_tab(), "Log de atividades")
        self.tabs.addTab(self._about_tab(), "Sobre")
        layout.addWidget(self.tabs, 1)

        admin = ctx.can(Permission.USER_MANAGE)
        self.tabs.setTabEnabled(0, admin)
        self.tabs.setTabEnabled(2, ctx.can(Permission.LOG_VIEW))

    # ----- usuários -------------------------------------------------
    def _users_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        bar = QHBoxLayout()
        new_user = primary_button("Novo usuário", "user-plus")
        new_user.clicked.connect(self._new_user)
        change = button("Alterar senha", "shield")
        change.clicked.connect(self._change_password)
        toggle = danger_button("Ativar / desativar", "logout")
        toggle.clicked.connect(self._toggle_user)
        bar.addWidget(new_user)
        bar.addWidget(change)
        bar.addWidget(toggle)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.users_table = DataTable(
            ["Nome", "Usuário", "Papel", "Situação", "Último acesso"],
            stretch=0,
            sortable=False,
        )
        layout.addWidget(self.users_table, 1)
        return page

    def _new_user(self) -> None:
        if UserDialog(self.ctx, self).exec() == QDialog.DialogCode.Accepted:
            self.refresh()
            info(self, "Usuário", "Usuário criado com sucesso.")

    def _change_password(self) -> None:
        user_id = self.users_table.selected_key()
        if user_id is None:
            warn(self, "Usuários", "Selecione um usuário na lista.")
            return
        if PasswordDialog(self.ctx, user_id, self).exec() == QDialog.DialogCode.Accepted:
            info(self, "Senha", "Senha alterada com sucesso.")

    def _toggle_user(self) -> None:
        row = self.users_table.currentRow()
        user_id = self.users_table.selected_key()
        if user_id is None or row < 0:
            warn(self, "Usuários", "Selecione um usuário na lista.")
            return
        item = self.users_table.item(row, 3)
        active = bool(item and item.text() == "Ativo")
        try:
            user_service.set_active(user_id, not active, self.ctx.user)
        except (BusinessError, PermissionDenied) as exc:
            warn(self, "Usuários", str(exc))
            return
        self.refresh()

    # ----- acesso pelo celular --------------------------------------
    def _mobile_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card()
        card.body.addWidget(SectionTitle("SYS Mobile — rede local"))
        self.mobile_status = QLabel("Servidor desligado.")
        self.mobile_status.setObjectName("CardValue")
        card.body.addWidget(self.mobile_status)

        self.mobile_url = QLabel("—")
        self.mobile_url.setObjectName("Muted")
        self.mobile_url.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        card.body.addWidget(self.mobile_url)

        actions = QHBoxLayout()
        self.start_button = primary_button("Ativar acesso pelo celular", "wifi")
        self.start_button.clicked.connect(self._start_api)
        self.stop_button = danger_button("Desligar", "logout")
        self.stop_button.clicked.connect(self._stop_api)
        actions.addWidget(self.start_button)
        actions.addWidget(self.stop_button)
        actions.addStretch(1)
        card.body.addLayout(actions)
        layout.addWidget(card)

        hint = QLabel(
            "O celular acessa apenas pela rede Wi‑Fi da empresa, com login e token. "
            "O banco de dados nunca é exposto diretamente. "
            "Com o servidor ligado, abra o endereço acima no navegador do celular "
            "e use /docs para consultar as operações disponíveis."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch(1)

        allowed = self.ctx.can(Permission.API_CONTROL)
        self.start_button.setEnabled(allowed)
        self.stop_button.setEnabled(allowed)
        return page

    def _start_api(self) -> None:
        try:
            status = api_server.start()
        except RuntimeError as exc:
            error(self, "Acesso pelo celular", str(exc))
            return
        self._render_api_status(status.detail)

    def _stop_api(self) -> None:
        status = api_server.stop()
        self._render_api_status(status.detail)

    def _render_api_status(self, detail: str = "") -> None:
        status = api_server.status(detail)
        if status.running:
            self.mobile_status.setText("SYS Mobile disponível na rede local.")
            self.mobile_status.setStyleSheet(f"color: {GREEN};")
            self.mobile_url.setText(
                f"Endereço: {status.url}   •   IP: {status.host}   •   Porta: {status.port}"
            )
        else:
            self.mobile_status.setText("Servidor desligado.")
            self.mobile_status.setStyleSheet(f"color: {TEXT_MUTED};")
            self.mobile_url.setText(f"Porta configurada: {status.port}")
        self.start_button.setEnabled(
            not status.running and self.ctx.can(Permission.API_CONTROL)
        )
        self.stop_button.setEnabled(status.running and self.ctx.can(Permission.API_CONTROL))

    # ----- logs ------------------------------------------------------
    def _logs_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)
        self.logs_table = DataTable(
            ["Data e hora", "Usuário", "Ação", "Detalhes"], stretch=3, sortable=False
        )
        layout.addWidget(self.logs_table, 1)
        return page

    # ----- sobre -----------------------------------------------------
    def _about_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)
        card = Card()
        card.body.addWidget(SectionTitle(APP_NAME))
        for text in (
            f"Versão {APP_VERSION}",
            f"Senhas protegidas com {algorithm()}",
            "Dados armazenados apenas no computador da empresa.",
            "Coleta mínima de dados pessoais: nome, CPF e telefone (LGPD).",
        ):
            label = QLabel(text)
            label.setObjectName("Muted")
            card.body.addWidget(label)
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    # ----- atualização ------------------------------------------------
    def refresh(self) -> None:
        if self.ctx.can(Permission.USER_MANAGE):
            rows = []
            for user in user_service.list_users(self.ctx.user):
                rows.append(
                    [
                        text_item(user.nome, key=user.id),
                        text_item(user.usuario),
                        text_item(user.papel),
                        text_item("Ativo" if user.ativo else "Inativo"),
                        text_item(format_datetime_br(user.ultimo_acesso)),
                    ]
                )
                if not user.ativo:
                    rows[-1][3].setForeground(QColor(RED))
            self.users_table.fill(rows)

        if self.ctx.can(Permission.LOG_VIEW):
            with session_scope() as session:
                entries = [
                    [
                        text_item(format_datetime_br(entry.criado_em), key=entry.id),
                        text_item(entry.usuario_nome),
                        text_item(entry.acao),
                        text_item(entry.detalhes or "—"),
                    ]
                    for entry in log_service.latest(session, limit=300)
                ]
            self.logs_table.fill(entries)

        self._render_api_status()
