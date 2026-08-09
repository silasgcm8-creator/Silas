"""Configurações: usuários, acesso pelo celular e log de atividades."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.api.server import api_server
from app.config import APP_NAME, APP_VERSION, settings
from app.models.status import Role
from app.security.password import algorithm
from app.security.permissions import Permission, PermissionDenied
from app.services import backup_service, log_service, slip_service, user_service
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
        self.tabs.addTab(self._company_tab(), "Empresa e Pix")
        self.tabs.addTab(self._backup_tab(), "Backup automático")
        self.tabs.addTab(self._mobile_tab(), "Acesso pelo celular")
        self.tabs.addTab(self._logs_tab(), "Log de atividades")
        self.tabs.addTab(self._about_tab(), "Sobre")
        layout.addWidget(self.tabs, 1)

        admin = ctx.can(Permission.USER_MANAGE)
        self.tabs.setTabEnabled(0, admin)
        self.tabs.setTabEnabled(1, ctx.can(Permission.SETTINGS))
        self.tabs.setTabEnabled(2, ctx.can(Permission.SETTINGS))
        self.tabs.setTabEnabled(4, ctx.can(Permission.LOG_VIEW))

    # ----- empresa e Pix ---------------------------------------------
    def _company_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        self.company_name = QLineEdit()
        self.company_name.setMinimumHeight(38)
        self.company_name.setPlaceholderText("Nome que aparece nos comprovantes e carnês")
        form.addRow(field_label("NOME DA EMPRESA"), self.company_name)

        self.pix_key = QLineEdit()
        self.pix_key.setMinimumHeight(38)
        self.pix_key.setPlaceholderText("CPF/CNPJ, e-mail, telefone ou chave aleatória")
        form.addRow(field_label("CHAVE PIX"), self.pix_key)

        self.pix_city = QLineEdit()
        self.pix_city.setMinimumHeight(38)
        self.pix_city.setPlaceholderText("Cidade da empresa")
        form.addRow(field_label("CIDADE"), self.pix_city)
        layout.addLayout(form)

        salvar = primary_button("Salvar dados da empresa", "check")
        salvar.clicked.connect(self._save_company)
        linha = QHBoxLayout()
        linha.addWidget(salvar)
        linha.addStretch(1)
        layout.addLayout(linha)

        self.company_hint = QLabel("")
        self.company_hint.setObjectName("Muted")
        self.company_hint.setWordWrap(True)
        layout.addWidget(self.company_hint)
        layout.addStretch(1)

        self._load_company()
        return page

    def _load_company(self) -> None:
        nome, chave, cidade = slip_service.company_settings()
        self.company_name.setText(nome)
        self.pix_key.setText(chave)
        self.pix_city.setText(cidade)
        if chave:
            self.company_hint.setText(
                "Com a chave cadastrada, o carnê de pagamento sai com QR Code e "
                "copia e cola do Pix da empresa. O valor levado é o saldo devedor "
                "do crediário."
            )
        else:
            self.company_hint.setText(
                "Sem chave Pix, o carnê é emitido com a área do Pix reservada em "
                "branco. O sistema nunca inventa dados bancários."
            )

    def _save_company(self) -> None:
        try:
            slip_service.save_company_settings(
                self.company_name.text(),
                self.pix_key.text(),
                self.pix_city.text(),
                self.ctx.user,
            )
        except (BusinessError, PermissionDenied) as exc:
            warn(self, "Empresa e Pix", str(exc))
            return
        self._load_company()
        self.ctx.notify("Dados da empresa salvos.")

    # ----- backup automático ----------------------------------------
    def _backup_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        self.auto_enabled = QCheckBox("Criar backup automaticamente")
        form.addRow(field_label("BACKUP AUTOMÁTICO"), self.auto_enabled)

        self.auto_hours = QSpinBox()
        self.auto_hours.setRange(1, 720)
        self.auto_hours.setSuffix(" hora(s)")
        self.auto_hours.setMinimumHeight(38)
        form.addRow(field_label("A CADA"), self.auto_hours)

        self.auto_keep = QSpinBox()
        self.auto_keep.setRange(1, 365)
        self.auto_keep.setSuffix(" cópia(s)")
        self.auto_keep.setMinimumHeight(38)
        form.addRow(field_label("MANTER AS ÚLTIMAS"), self.auto_keep)

        pasta_linha = QHBoxLayout()
        self.auto_folder = QLineEdit()
        self.auto_folder.setMinimumHeight(38)
        self.auto_folder.setPlaceholderText("Pasta padrão do sistema")
        escolher = button("Escolher pasta", "list")
        escolher.clicked.connect(self._choose_backup_folder)
        pasta_linha.addWidget(self.auto_folder, 1)
        pasta_linha.addWidget(escolher)
        form.addRow(field_label("PASTA"), pasta_linha)
        layout.addLayout(form)

        acoes = QHBoxLayout()
        salvar = primary_button("Salvar configuração", "check")
        salvar.clicked.connect(self._save_backup_config)
        agora = button("Criar backup automático agora", "download")
        agora.clicked.connect(self._run_backup_now)
        acoes.addWidget(salvar)
        acoes.addWidget(agora)
        acoes.addStretch(1)
        layout.addLayout(acoes)

        self.auto_status = QLabel("")
        self.auto_status.setObjectName("Muted")
        self.auto_status.setWordWrap(True)
        layout.addWidget(self.auto_status)
        layout.addStretch(1)

        self._load_backup_config()
        return page

    def _load_backup_config(self) -> None:
        config = backup_service.auto_config()
        self.auto_enabled.setChecked(config.enabled)
        self.auto_hours.setValue(config.interval_hours)
        self.auto_keep.setValue(config.keep)
        if config.folder != settings.backup_dir:
            self.auto_folder.setText(str(config.folder))
        quando = (
            format_datetime_br(config.last_run) if config.last_run else "ainda não rodou"
        )
        self.auto_status.setText(
            f"Último backup automático: {quando}. Pasta em uso: {config.folder}. "
            "A cópia é feita quando o programa abre, se já passou do intervalo. "
            "Backups manuais e as cópias feitas antes de uma restauração nunca "
            "são apagados pela limpeza automática."
        )

    def _choose_backup_folder(self) -> None:
        atual = self.auto_folder.text().strip() or str(settings.backup_dir)
        escolhida = QFileDialog.getExistingDirectory(
            self, "Pasta dos backups automáticos", atual
        )
        if escolhida:
            self.auto_folder.setText(escolhida)

    def _save_backup_config(self) -> None:
        try:
            backup_service.save_auto_config(
                enabled=self.auto_enabled.isChecked(),
                interval_hours=self.auto_hours.value(),
                folder=self.auto_folder.text().strip() or None,
                keep=self.auto_keep.value(),
                actor=self.ctx.user,
            )
        except (BusinessError, PermissionDenied) as exc:
            warn(self, "Backup automático", str(exc))
            return
        self._load_backup_config()
        self.ctx.notify("Configuração de backup salva.")

    def _run_backup_now(self) -> None:
        try:
            caminho = backup_service.auto_backup_if_due(force=True)
        except (BusinessError, PermissionDenied) as exc:
            warn(self, "Backup automático", str(exc))
            return
        if caminho is None:
            warn(
                self,
                "Backup automático",
                "Não foi possível gravar o backup. Confira se a pasta escolhida "
                "está acessível — o detalhe técnico foi gravado no log.",
            )
            return
        self._load_backup_config()
        info(self, "Backup criado", f"Arquivo gerado:\n{caminho}")

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
