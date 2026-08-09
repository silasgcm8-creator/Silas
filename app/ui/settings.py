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
from app.models.charge import CHARGE_TYPE_LABELS, TYPE_BANK, TYPE_REGISTERED, TYPE_STORE
from app.services import (
    backup_service,
    bank_account_service,
    charge_service,
    company_service,
    log_service,
    slip_service,
    user_service,
)
from app.services.errors import BusinessError, ValidationError
from app.ui.context import AppContext
from app.ui.theme import GREEN, RED, TEXT_MUTED
from app.ui.widgets import (
    Card,
    DataTable,
    SectionTitle,
    button,
    confirm,
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
from app.utils.validators import format_phone
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
        self.tabs.addTab(self._company_tab(), "Identidade e Pix")
        self.tabs.addTab(self._banks_tab(), "Bancos e recebimentos")
        self.tabs.addTab(self._charges_tab(), "Cobranças")
        self.tabs.addTab(self._backup_tab(), "Backup automático")
        self.tabs.addTab(self._mobile_tab(), "Acesso pelo celular")
        self.tabs.addTab(self._logs_tab(), "Log de atividades")
        self.tabs.addTab(self._about_tab(), "Sobre")
        layout.addWidget(self.tabs, 1)

        admin = ctx.can(Permission.USER_MANAGE)
        self.tabs.setTabEnabled(0, admin)
        self.tabs.setTabEnabled(1, ctx.can(Permission.SETTINGS))
        self.tabs.setTabEnabled(2, ctx.can(Permission.BANK_MANAGE))
        self.tabs.setTabEnabled(3, ctx.can(Permission.SETTINGS))
        self.tabs.setTabEnabled(4, ctx.can(Permission.SETTINGS))
        self.tabs.setTabEnabled(6, ctx.can(Permission.LOG_VIEW))

    # ----- identidade e recebimento -----------------------------------
    def _company_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        aviso = QLabel(
            f"Os documentos usam somente o nome <b>{company_service.profile().titulo}</b>. "
            "Não há cadastro de razão social, CNPJ, endereço ou telefone."
        )
        aviso.setWordWrap(True)
        layout.addWidget(aviso)

        form = QFormLayout()
        form.setSpacing(10)

        logo_linha = QHBoxLayout()
        self.logo_label = QLabel("Nenhum logotipo cadastrado")
        self.logo_label.setObjectName("Muted")
        escolher_logo = button("Escolher logotipo", "upload")
        escolher_logo.clicked.connect(self._choose_logo)
        remover_logo = button("Remover", "logout", ghost=True)
        remover_logo.clicked.connect(self._remove_logo)
        logo_linha.addWidget(self.logo_label, 1)
        logo_linha.addWidget(escolher_logo)
        logo_linha.addWidget(remover_logo)
        form.addRow(field_label("LOGOTIPO (OPCIONAL)"), logo_linha)

        self.pix_key = QLineEdit()
        self.pix_key.setMinimumHeight(38)
        self.pix_key.setPlaceholderText("CPF/CNPJ, e-mail, telefone ou chave aleatória")
        form.addRow(field_label("CHAVE PIX DO CARNÊ"), self.pix_key)

        self.pix_city = QLineEdit()
        self.pix_city.setMinimumHeight(38)
        self.pix_city.setPlaceholderText("Cidade usada no QR Code do Pix")
        form.addRow(field_label("CIDADE DO PIX"), self.pix_city)
        layout.addLayout(form)

        salvar = primary_button("Salvar", "check")
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
        perfil = company_service.profile()
        self.logo_label.setText(
            f"Logotipo: {perfil.logo.name}" if perfil.tem_logo
            else "Nenhum logotipo cadastrado"
        )
        chave, cidade = slip_service.pix_settings()
        self.pix_key.setText(chave)
        self.pix_city.setText(cidade)
        self.company_hint.setText(
            "Com a chave Pix cadastrada, o carnê traz o QR Code e o copia e cola. "
            "Sem chave, a área do Pix fica reservada em branco — o sistema nunca "
            "inventa dados bancários."
        )

    def _choose_logo(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self,
            "Escolher logotipo",
            str(settings.base_dir),
            "Imagens (*.png *.jpg *.jpeg *.gif)",
        )
        if not caminho:
            return
        try:
            company_service.save_logo(caminho, self.ctx.user)
        except (BusinessError, PermissionDenied) as exc:
            warn(self, "Logotipo", str(exc))
            return
        self._load_company()
        self.ctx.notify("Logotipo cadastrado.")

    def _remove_logo(self) -> None:
        try:
            company_service.remove_logo(self.ctx.user)
        except (BusinessError, PermissionDenied) as exc:
            warn(self, "Logotipo", str(exc))
            return
        self._load_company()
        self.ctx.notify("Logotipo removido dos documentos.")

    def _save_company(self) -> None:
        try:
            slip_service.save_pix_settings(
                self.pix_key.text(), self.pix_city.text(), self.ctx.user
            )
        except (BusinessError, PermissionDenied) as exc:
            warn(self, "Recebimento", str(exc))
            return
        self._load_company()
        self.ctx.notify("Dados salvos.")

    # ----- bancos e recebimentos --------------------------------------
    def _banks_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        aviso = QLabel(
            "Somente o administrador cadastra e altera contas. O funcionário "
            "apenas escolhe uma conta já autorizada ao emitir a cobrança."
        )
        aviso.setObjectName("Muted")
        aviso.setWordWrap(True)
        layout.addWidget(aviso)

        bar = QHBoxLayout()
        nova = primary_button("Nova conta", "plus")
        nova.clicked.connect(self._new_account)
        editar = button("Editar", "users")
        editar.clicked.connect(self._edit_account)
        alternar = button("Ativar / desativar", "check")
        alternar.clicked.connect(self._toggle_account)
        excluir = danger_button("Excluir", "logout")
        excluir.clicked.connect(self._delete_account)
        for widget in (nova, editar, alternar, excluir):
            bar.addWidget(widget)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.accounts_table = DataTable(
            ["Identificação", "Banco", "Agência", "Conta", "Beneficiário", "PIX", "Situação"],
            stretch=1,
            sortable=False,
        )
        layout.addWidget(self.accounts_table, 1)
        self._load_accounts()
        return page

    def _load_accounts(self) -> None:
        contas = bank_account_service.list_accounts(only_active=False)
        self.accounts_table.fill(
            [
                [
                    text_item(conta.identificacao, key=conta.id),
                    text_item(conta.banco or "—"),
                    text_item(conta.agencia or "—"),
                    text_item(conta.conta or "—"),
                    text_item(conta.beneficiario or "—"),
                    text_item(conta.pix or "—"),
                    text_item("Ativa" if conta.ativa else "Desativada"),
                ]
                for conta in contas
            ]
        )

    def _new_account(self) -> None:
        from app.ui.bank_dialog import BankAccountDialog

        if BankAccountDialog(self.ctx, None, self).exec() == QDialog.DialogCode.Accepted:
            self._load_accounts()

    def _edit_account(self) -> None:
        from app.ui.bank_dialog import BankAccountDialog

        account_id = self.accounts_table.selected_key()
        if account_id is None:
            warn(self, "Contas", "Selecione uma conta na lista.")
            return
        if BankAccountDialog(self.ctx, account_id, self).exec() == QDialog.DialogCode.Accepted:
            self._load_accounts()

    def _toggle_account(self) -> None:
        account_id = self.accounts_table.selected_key()
        if account_id is None:
            warn(self, "Contas", "Selecione uma conta na lista.")
            return
        try:
            conta = bank_account_service.get_account(account_id)
            bank_account_service.set_active(account_id, not conta.ativa, self.ctx.user)
        except (BusinessError, PermissionDenied) as exc:
            warn(self, "Contas", str(exc))
            return
        self._load_accounts()
        self.ctx.notify("Conta atualizada.")

    def _delete_account(self) -> None:
        account_id = self.accounts_table.selected_key()
        if account_id is None:
            warn(self, "Contas", "Selecione uma conta na lista.")
            return
        if not confirm(
            self,
            "Excluir conta",
            "Se a conta já foi usada em alguma cobrança, ela será apenas "
            "desativada — para não apagar informação de documento emitido.\n\n"
            "Continuar?",
        ):
            return
        try:
            bank_account_service.delete_account(account_id, self.ctx.user)
        except (BusinessError, PermissionDenied) as exc:
            warn(self, "Contas", str(exc))
            return
        self._load_accounts()
        self.ctx.notify("Conta removida ou desativada.")

    # ----- modalidades de cobrança -----------------------------------
    def _charges_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        layout.addWidget(field_label("FORMAS PERMITIDAS"))
        self.charge_checks: dict[str, QCheckBox] = {}
        for tipo in (TYPE_STORE, TYPE_BANK, TYPE_REGISTERED):
            caixa = QCheckBox(CHARGE_TYPE_LABELS[tipo])
            if tipo == TYPE_REGISTERED:
                caixa.setToolTip(
                    "Só funciona com integração oficial contratada com o banco."
                )
            layout.addWidget(caixa)
            self.charge_checks[tipo] = caixa

        layout.addWidget(field_label("FORMA PADRÃO DE COBRANÇA"))
        self.charge_default = QComboBox()
        self.charge_default.setMinimumHeight(38)
        self.charge_default.addItem("Perguntar sempre", charge_service.ASK_ALWAYS)
        for tipo in (TYPE_STORE, TYPE_BANK):
            self.charge_default.addItem(CHARGE_TYPE_LABELS[tipo], tipo)
        layout.addWidget(self.charge_default)

        salvar = primary_button("Salvar formas de cobrança", "check")
        salvar.clicked.connect(self._save_charge_settings)
        linha = QHBoxLayout()
        linha.addWidget(salvar)
        linha.addStretch(1)
        layout.addLayout(linha)

        self.charge_hint = QLabel(
            "Boleto bancário registrado depende de integração oficial. Enquanto "
            "não houver, a emissão é recusada — o sistema não cria linha "
            "digitável nem código de barras bancário."
        )
        self.charge_hint.setObjectName("Muted")
        self.charge_hint.setWordWrap(True)
        layout.addWidget(self.charge_hint)
        layout.addStretch(1)

        self._load_charge_settings()
        return page

    def _load_charge_settings(self) -> None:
        permitidas = charge_service.allowed_types()
        for tipo, caixa in self.charge_checks.items():
            caixa.setChecked(tipo in permitidas)
        indice = self.charge_default.findData(charge_service.default_type())
        self.charge_default.setCurrentIndex(max(0, indice))

    def _save_charge_settings(self) -> None:
        escolhidas = [tipo for tipo, caixa in self.charge_checks.items() if caixa.isChecked()]
        try:
            charge_service.save_charge_settings(
                escolhidas, self.charge_default.currentData(), self.ctx.user
            )
        except (BusinessError, PermissionDenied) as exc:
            warn(self, "Cobranças", str(exc))
            return
        self._load_charge_settings()
        self.ctx.notify("Formas de cobrança salvas.")

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
