"""Clientes: cadastro, pesquisa e ficha financeira."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app.security.permissions import Permission, PermissionDenied
from app.services import charge_service, client_service, credit_service
from app.services.errors import BusinessError, NotFoundError, ValidationError
from app.ui import icons
from app.ui.context import AppContext
from app.ui.credits import CreditDetailDialog, NewCreditDialog, open_charge_whatsapp
from app.ui.theme import ACCENT, GREEN, PURPLE, RED, TEXT_MUTED, YELLOW
from app.ui.widgets import (
    Card,
    DataTable,
    MetricCard,
    SearchBox,
    SectionTitle,
    button,
    danger_button,
    date_item,
    error,
    field_label,
    info,
    money_item,
    number_item,
    page_header,
    primary_button,
    text_item,
    warn,
)
from app.utils.cpf import format_cpf
from app.utils.dates import format_datetime_br
from app.utils.money import ZERO, format_brl
from app.utils.validators import format_phone


class ClientDialog(QDialog):
    """Cadastro e edição. O CPF é definido uma única vez."""

    def __init__(
        self,
        ctx: AppContext,
        client_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.client_id = client_id
        self.saved_id: int | None = None
        editing = client_id is not None
        self.setWindowTitle("Editar cliente" if editing else "Novo cliente")
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)
        layout.addWidget(
            page_header(
                "Editar cliente" if editing else "Novo cliente",
                "Nome, CPF e telefone — nada além do necessário",
            )
        )

        card = Card()
        form = QFormLayout()
        form.setSpacing(10)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nome completo")
        self.cpf_edit = QLineEdit()
        self.cpf_edit.setPlaceholderText("000.000.000-00")
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("(00) 00000-0000")

        self.cpf_edit.textChanged.connect(self._mask_cpf)
        self.phone_edit.textChanged.connect(self._mask_phone)

        form.addRow(field_label("NOME COMPLETO"), self.name_edit)
        form.addRow(field_label("CPF"), self.cpf_edit)
        form.addRow(field_label("TELEFONE"), self.phone_edit)
        card.body.addLayout(form)
        layout.addWidget(card)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel = button("Cancelar", ghost=True)
        cancel.clicked.connect(self.reject)
        save = primary_button("Salvar cliente", "check")
        save.clicked.connect(self._save)
        actions.addWidget(cancel)
        actions.addWidget(save)
        layout.addLayout(actions)

        if editing:
            client = client_service.get_client(client_id)  # type: ignore[arg-type]
            self.name_edit.setText(client.nome)
            self.cpf_edit.setText(client.cpf)
            self.cpf_edit.setReadOnly(True)
            self.cpf_edit.setToolTip("O CPF não pode ser alterado após o cadastro.")
            self.phone_edit.setText(client.telefone)
        self.name_edit.setFocus()

    def _mask_cpf(self, text: str) -> None:
        masked = format_cpf(text)
        if masked != text:
            self.cpf_edit.blockSignals(True)
            self.cpf_edit.setText(masked)
            self.cpf_edit.setCursorPosition(len(masked))
            self.cpf_edit.blockSignals(False)

    def _mask_phone(self, text: str) -> None:
        masked = format_phone(text)
        if masked != text:
            self.phone_edit.blockSignals(True)
            self.phone_edit.setText(masked)
            self.phone_edit.setCursorPosition(len(masked))
            self.phone_edit.blockSignals(False)

    def _save(self) -> None:
        try:
            if self.client_id is None:
                self.saved_id = client_service.create_client(
                    self.name_edit.text(),
                    self.cpf_edit.text(),
                    self.phone_edit.text(),
                    self.ctx.user,
                )
            else:
                client_service.update_client(
                    self.client_id,
                    self.name_edit.text(),
                    self.phone_edit.text(),
                    self.ctx.user,
                )
                self.saved_id = self.client_id
        except (ValidationError, BusinessError, PermissionDenied) as exc:
            warn(self, "Cadastro", str(exc))
            return
        self.ctx.notify("Cliente salvo.")
        self.accept()


class ClientDetailDialog(QDialog):
    """Ficha financeira completa do cliente."""

    def __init__(self, ctx: AppContext, client_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.client_id = client_id
        self.setWindowTitle("Ficha do cliente")
        self.setMinimumSize(860, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        self.header = page_header("Cliente", "carregando...")
        layout.addWidget(self.header)

        self.identity = QLabel("")
        self.identity.setObjectName("Muted")
        layout.addWidget(self.identity)

        cards = QGridLayout()
        cards.setSpacing(12)
        self.card_comprado = MetricCard("Total comprado", "cash", ACCENT)
        self.card_pago = MetricCard("Total pago", "check", GREEN)
        self.card_aberto = MetricCard("Total em aberto", "list", YELLOW)
        self.card_vencido = MetricCard("Total vencido", "alert", RED)
        self.card_saldo = MetricCard("Saldo devedor", "chart", PURPLE)
        for index, card in enumerate(
            (
                self.card_comprado,
                self.card_pago,
                self.card_aberto,
                self.card_vencido,
                self.card_saldo,
            )
        ):
            cards.addWidget(card, index // 3, index % 3)
        layout.addLayout(cards)

        layout.addWidget(SectionTitle("Crediários do cliente"))
        self.table = DataTable(
            ["Crediário", "Compra", "Parcelas", "Pago", "Saldo", "Vencido", "1º vencimento"],
            stretch=None,
            sortable=False,
        )
        self.table.doubleClicked.connect(lambda *_: self._open_credit())
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        open_credit = primary_button("Abrir crediário", "list")
        open_credit.clicked.connect(self._open_credit)
        new_credit = button("Novo crediário", "plus")
        new_credit.clicked.connect(self._new_credit)
        new_credit.setEnabled(ctx.can(Permission.CREDIT_CREATE))
        edit = button("Editar cadastro", "users")
        edit.clicked.connect(self._edit)
        edit.setEnabled(ctx.can(Permission.CLIENT_EDIT))
        whats = button("WhatsApp", "whatsapp")
        whats.clicked.connect(self._whatsapp)
        close = button("Fechar", ghost=True)
        close.clicked.connect(self.accept)

        for widget in (open_credit, new_credit, edit, whats):
            actions.addWidget(widget)
        actions.addStretch(1)
        actions.addWidget(close)
        layout.addLayout(actions)

        self.refresh()

    def refresh(self) -> None:
        try:
            summary = client_service.get_summary(self.client_id)
        except NotFoundError as exc:
            error(self, "Cliente", str(exc))
            self.reject()
            return

        self.summary = summary
        title = self.header.findChild(QLabel, "PageTitle")
        if title is not None:
            title.setText(summary.nome)
        subtitle = self.header.findChild(QLabel, "PageSubtitle")
        if subtitle is not None:
            subtitle.setText("Ficha financeira")
        self.identity.setText(f"{summary.cpf}   •   {summary.telefone}")

        self.card_comprado.set_value(format_brl(summary.total_comprado))
        self.card_pago.set_value(format_brl(summary.total_pago), color=GREEN)
        self.card_aberto.set_value(format_brl(summary.total_aberto))
        self.card_vencido.set_value(
            format_brl(summary.total_vencido),
            color=RED if summary.total_vencido > ZERO else None,
        )
        self.card_saldo.set_value(format_brl(summary.saldo_devedor))

        rows = []
        for credit in credit_service.list_by_client(self.client_id):
            vencido = credit["vencido"]
            rows.append(
                [
                    text_item(f"#{credit['id']}", key=int(credit["id"]), bold=True),
                    money_item(credit["valor_total"]),
                    number_item(int(credit["parcelas"])),
                    money_item(credit["pago"], color=GREEN),
                    money_item(credit["saldo"]),
                    money_item(vencido, color=RED if vencido > ZERO else TEXT_MUTED),
                    date_item(credit["primeiro_vencimento"]),
                ]
            )
        self.table.fill(rows)
        if rows:
            self.table.selectRow(0)

    def _selected_credit(self) -> int | None:
        credit_id = self.table.selected_key()
        if credit_id is None:
            warn(self, "Crediário", "Selecione um crediário na lista.")
        return credit_id

    def _open_credit(self) -> None:
        credit_id = self._selected_credit()
        if credit_id is None:
            return
        CreditDetailDialog(self.ctx, credit_id, self).exec()
        self.refresh()

    def _new_credit(self) -> None:
        dialog = NewCreditDialog(self.ctx, self.client_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _edit(self) -> None:
        dialog = ClientDialog(self.ctx, self.client_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _whatsapp(self) -> None:
        open_charge_whatsapp(
            self, self.client_id, self.summary.nome, self.summary.telefone
        )


class DeletedClientsDialog(QDialog):
    """Cadastros excluídos logicamente, com opção de reativar."""

    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Cadastros excluídos")
        self.setMinimumSize(820, 460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)
        layout.addWidget(
            page_header(
                "Cadastros excluídos",
                "A exclusão é lógica: nada foi apagado do banco",
            )
        )

        self.table = DataTable(
            ["Nome", "CPF", "Telefone", "Excluído em", "Por", "Motivo"],
            stretch=5,
            sortable=False,
        )
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        restore = primary_button("Reativar cadastro", "undo")
        restore.clicked.connect(self._restore)
        close = button("Fechar", ghost=True)
        close.clicked.connect(self.accept)
        actions.addWidget(restore)
        actions.addStretch(1)
        actions.addWidget(close)
        layout.addLayout(actions)

        self.hint = QLabel("")
        self.hint.setObjectName("Muted")
        layout.addWidget(self.hint)

        self.refresh()

    def refresh(self) -> None:
        rows = client_service.list_deleted(self.ctx.user)
        self.table.fill(
            [
                [
                    text_item(row.nome, key=row.id),
                    text_item(row.cpf),
                    text_item(row.telefone),
                    text_item(format_datetime_br(row.excluido_em)),
                    text_item(row.excluido_por),
                    text_item(row.motivo),
                ]
                for row in rows
            ]
        )
        self.hint.setText(
            "Nenhum cadastro excluído."
            if not rows
            else f"{len(rows)} cadastro(s) excluído(s). Reativar devolve o cliente "
            "às listas com todo o histórico."
        )

    def _restore(self) -> None:
        client_id = self.table.selected_key()
        if client_id is None:
            warn(self, "Reativar", "Selecione um cadastro na lista.")
            return
        try:
            client_service.restore_client(client_id, self.ctx.user)
        except (BusinessError, NotFoundError, PermissionDenied) as exc:
            warn(self, "Reativar", str(exc))
            return
        self.ctx.notify("Cadastro reativado.")
        self.refresh()


class ClientsPage(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._term = ""
        self._page = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(
            page_header("Clientes", "Pesquise por nome, CPF ou telefone")
        )

        bar = QHBoxLayout()
        self.search = SearchBox("Digite o nome, o CPF ou o telefone")
        self.search.search.connect(self._on_search)
        self.search.returnPressed.connect(self._open_exact_cpf)
        bar.addWidget(self.search, 1)

        new_button = primary_button("Novo cliente", "user-plus")
        new_button.clicked.connect(self.new_client)
        new_button.setEnabled(ctx.can(Permission.CLIENT_CREATE))
        bar.addWidget(new_button)

        # Exclusão só para administrador, e é lógica: nada sai do banco.
        if ctx.can(Permission.CLIENT_DELETE):
            delete_button = danger_button("Excluir cadastro", "logout")
            delete_button.clicked.connect(self._delete_selected)
            bar.addWidget(delete_button)

            deleted_button = button("Cadastros excluídos", "list", ghost=True)
            deleted_button.clicked.connect(self._show_deleted)
            bar.addWidget(deleted_button)
        layout.addLayout(bar)

        self.table = DataTable(
            [
                "Nome completo",
                "CPF",
                "Telefone",
                "Saldo devedor",
                "Valor vencido",
                "Ações",
            ],
            stretch=0,
            sortable=False,
        )
        self.table.doubleClicked.connect(lambda *_: self._open_selected())
        layout.addWidget(self.table, 1)

        rodape = QHBoxLayout()
        self.total_label = QLabel("")
        self.total_label.setObjectName("Muted")
        rodape.addWidget(self.total_label, 1)

        self.prev_button = button("Anterior", "undo", ghost=True)
        self.prev_button.clicked.connect(lambda *_: self._change_page(-1))
        self.next_button = button("Próxima", "list", ghost=True)
        self.next_button.clicked.connect(lambda *_: self._change_page(1))
        self.page_label = QLabel("")
        self.page_label.setObjectName("Muted")
        rodape.addWidget(self.prev_button)
        rodape.addWidget(self.page_label)
        rodape.addWidget(self.next_button)
        layout.addLayout(rodape)

    def _on_search(self, term: str) -> None:
        self._term = term
        self._page = 0  # nova busca sempre começa na primeira página
        self.refresh()

    def _change_page(self, delta: int) -> None:
        self._page = max(0, self._page + delta)
        self.refresh()

    def refresh(self) -> None:
        total = client_service.count_clients(self._term)
        tamanho = client_service.PAGE_SIZE
        ultima = max(0, (total - 1) // tamanho) if total else 0
        self._page = min(self._page, ultima)
        rows = client_service.list_clients(
            self._term, limit=tamanho, offset=self._page * tamanho
        )
        self.table.fill(
            [
                [
                    text_item(row.nome, key=row.id),
                    text_item(row.cpf),
                    text_item(row.telefone),
                    money_item(row.saldo),
                    money_item(row.vencido, color=RED if row.vencido > ZERO else TEXT_MUTED),
                    text_item(""),
                ]
                for row in rows
            ]
        )
        for index, row in enumerate(rows):
            self.table.setCellWidget(index, 5, self._actions(row.id, row.nome, row.telefone))
        self.table.setColumnWidth(5, 140)
        # Totais somados no banco, sobre toda a busca — não apenas a página.
        saldo, vencido = client_service.search_totals(self._term)
        primeiro = self._page * tamanho + 1 if rows else 0
        ultimo = self._page * tamanho + len(rows)
        faixa = f"{primeiro}–{ultimo} de {total}" if total else "nenhum cliente"
        self.total_label.setText(
            f"Mostrando {faixa}   •   saldo {format_brl(saldo)}   •   "
            f"vencido {format_brl(vencido)}"
        )
        self.page_label.setText(f"Página {self._page + 1} de {ultima + 1}")
        self.prev_button.setEnabled(self._page > 0)
        self.next_button.setEnabled(self._page < ultima)

    def _actions(self, client_id: int, nome: str, telefone: str) -> QWidget:
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(4)

        def small(icon_name: str, tip: str, color: str) -> QWidget:
            widget = button("")
            widget.setIcon(icons.icon(icon_name, color, 15))
            widget.setToolTip(tip)
            widget.setFixedSize(34, 30)
            return widget

        open_button = small("list", "Abrir ficha", ACCENT)
        open_button.clicked.connect(lambda: self.open_client(client_id))
        edit_button = small("users", "Editar cadastro", TEXT_MUTED)
        edit_button.clicked.connect(lambda: self._edit(client_id))
        edit_button.setEnabled(self.ctx.can(Permission.CLIENT_EDIT))
        whats_button = small("whatsapp", "Enviar cobrança pelo WhatsApp", GREEN)
        whats_button.clicked.connect(
            lambda: open_charge_whatsapp(self, client_id, nome, telefone)
        )
        whats_button.setEnabled(self.ctx.can(Permission.WHATSAPP))

        row.addWidget(open_button)
        row.addWidget(edit_button)
        row.addWidget(whats_button)
        row.addStretch(1)
        return holder

    def _open_selected(self) -> None:
        client_id = self.table.selected_key()
        if client_id is None:
            warn(self, "Cliente", "Selecione um cliente na lista.")
            return
        self.open_client(client_id)

    def _open_exact_cpf(self) -> None:
        """Enter abre direto: aceita CPF cadastrado ou código de cobrança.

        O número do documento é o conteúdo do QR interno, então o atendente pode
        digitá-lo (ou ler com leitor) na mesma busca.
        """
        term = self.search.text().strip()

        cobranca = charge_service.find_by_number(term)
        if cobranca is not None:
            self.open_credit(cobranca.crediario_id)
            return

        client = client_service.find_by_cpf(term)
        if client is not None:
            self.open_client(client.id)

    def open_credit(self, credit_id: int) -> None:
        CreditDetailDialog(self.ctx, credit_id, self).exec()
        self.refresh()

    def open_client(self, client_id: int) -> None:
        ClientDetailDialog(self.ctx, client_id, self).exec()
        self.refresh()

    def _edit(self, client_id: int) -> None:
        dialog = ClientDialog(self.ctx, client_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _delete_selected(self) -> None:
        """Exclusão lógica com confirmação do CPF e motivo registrado."""
        client_id = self.table.selected_key()
        if client_id is None:
            warn(self, "Excluir cadastro", "Selecione um cliente na lista.")
            return
        client = client_service.get_client(client_id)

        if not client_service.can_delete(client_id):
            warn(
                self,
                "Excluir cadastro",
                f"{client.nome} possui histórico financeiro e não pode ser "
                "excluído. O cadastro é mantido para preservar a auditoria.",
            )
            return

        cpf, ok = QInputDialog.getText(
            self,
            "Excluir cadastro",
            f"Esta ação retira {client.nome} das listas. O cadastro continua no\n"
            "banco e pode ser reativado depois.\n\nPara confirmar, digite o CPF "
            "do cliente:",
        )
        if not ok:
            return
        motivo, ok = QInputDialog.getText(
            self, "Excluir cadastro", "Motivo da exclusão (opcional):"
        )
        if not ok:
            return
        try:
            client_service.delete_client(client_id, self.ctx.user, cpf, motivo)
        except (BusinessError, NotFoundError, PermissionDenied) as exc:
            warn(self, "Excluir cadastro", str(exc))
            return
        self.ctx.notify("Cadastro excluído. Pode ser reativado em Cadastros excluídos.")
        self.refresh()

    def _show_deleted(self) -> None:
        DeletedClientsDialog(self.ctx, self).exec()
        self.refresh()

    def focus_search(self) -> None:
        """Deixa o cursor na pesquisa — é por onde todo atendimento começa."""
        self.search.setFocus()
        self.search.selectAll()

    def new_client(self) -> None:
        dialog = ClientDialog(self.ctx, None, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.saved_id:
            self.refresh()
            if self.ctx.can(Permission.CREDIT_CREATE):
                self.open_client(dialog.saved_id)
            else:
                info(self, "Cliente cadastrado", "Cliente salvo com sucesso.")
