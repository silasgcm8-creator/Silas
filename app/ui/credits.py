"""Crediários: listagem, criação e ficha de parcelas."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.services import client_service, credit_service, payment_service, report_service
from app.services.errors import BusinessError, NotFoundError, ValidationError
from app.security.permissions import Permission, PermissionDenied
from app.ui.context import AppContext
from app.ui.theme import ACCENT, GREEN, RED, TEXT_MUTED, YELLOW
from app.ui.widgets import (
    Card,
    DataTable,
    DateEdit,
    MetricCard,
    SearchBox,
    SectionTitle,
    button,
    confirm,
    danger_button,
    date_item,
    error,
    field_label,
    info,
    money_item,
    page_header,
    primary_button,
    status_item,
    text_item,
    warn,
)
from app.utils.money import ZERO, format_brl, parse_brl
from app.utils.whatsapp import OFFLINE_MESSAGE, build_message, open_whatsapp


def open_charge_whatsapp(parent: QWidget, client_id: int, nome: str, telefone: str) -> None:
    """Prepara a conversa de cobrança; o envio é sempre decisão do funcionário."""
    total, oldest, count = report_service.client_overdue_summary(client_id)
    if count == 0:
        info(parent, "Sem valores vencidos", f"{nome} não possui parcelas vencidas.")
        return
    message = build_message(nome, telefone, total, oldest, count)
    if not open_whatsapp(message):
        warn(parent, "WhatsApp", OFFLINE_MESSAGE)


class NewCreditDialog(QDialog):
    """Cadastro do crediário com simulação das parcelas antes de gravar."""

    def __init__(self, ctx: AppContext, client_id: int | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.created_id: int | None = None
        self.setWindowTitle("Novo crediário")
        self.setMinimumWidth(720)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)
        layout.addWidget(page_header("Novo crediário", "Gere as parcelas automaticamente"))

        form_card = Card()
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.client_search = SearchBox("Pesquise o cliente por nome ou CPF")
        self.client_combo = QComboBox()
        self.client_combo.setMinimumHeight(38)

        self.total_edit = QLineEdit()
        self.total_edit.setPlaceholderText("0,00")
        self.entry_edit = QLineEdit("0,00")
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 60)
        self.count_spin.setValue(1)
        self.count_spin.setMinimumHeight(38)
        self.first_due = DateEdit(date.today())
        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("Ex.: 2 pares de óculos (opcional)")

        form.addRow(field_label("CLIENTE"), self.client_search)
        form.addRow(QLabel(""), self.client_combo)
        form.addRow(field_label("VALOR TOTAL DA COMPRA (R$)"), self.total_edit)
        form.addRow(field_label("ENTRADA (R$)"), self.entry_edit)
        form.addRow(field_label("QUANTIDADE DE PARCELAS"), self.count_spin)
        form.addRow(field_label("PRIMEIRO VENCIMENTO"), self.first_due)
        form.addRow(field_label("DESCRIÇÃO"), self.description_edit)
        form_card.body.addLayout(form)
        layout.addWidget(form_card)

        self.summary = QLabel("Informe o valor da compra para simular as parcelas.")
        self.summary.setObjectName("Muted")
        layout.addWidget(self.summary)

        self.preview = DataTable(["Parcela", "Vencimento", "Valor"], stretch=0, sortable=False)
        self.preview.setMaximumHeight(200)
        layout.addWidget(self.preview)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel = button("Cancelar", ghost=True)
        cancel.clicked.connect(self.reject)
        self.save_button = primary_button("Criar crediário", "plus")
        self.save_button.clicked.connect(self._save)
        actions.addWidget(cancel)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)

        self.client_search.search.connect(self._load_clients)
        for widget in (self.total_edit, self.entry_edit):
            widget.textChanged.connect(lambda *_: self._update_preview())
        self.count_spin.valueChanged.connect(lambda *_: self._update_preview())
        self.first_due.dateChanged.connect(lambda *_: self._update_preview())

        self._load_clients("")
        if client_id is not None:
            index = self.client_combo.findData(client_id)
            if index >= 0:
                self.client_combo.setCurrentIndex(index)

    def _load_clients(self, term: str = "") -> None:
        current = self.client_combo.currentData()
        self.client_combo.clear()
        for row in client_service.list_clients(term):
            self.client_combo.addItem(f"{row.nome} — {row.cpf}", row.id)
        if current is not None:
            index = self.client_combo.findData(current)
            if index >= 0:
                self.client_combo.setCurrentIndex(index)

    def _update_preview(self) -> None:
        try:
            rows = credit_service.preview_installments(
                parse_brl(self.total_edit.text()),
                parse_brl(self.entry_edit.text()),
                self.count_spin.value(),
                self.first_due.get_date(),
            )
        except (ValidationError, ValueError):
            self.preview.fill([])
            self.summary.setText("Informe o valor da compra para simular as parcelas.")
            return

        total = parse_brl(self.total_edit.text())
        entry = parse_brl(self.entry_edit.text())
        financed = total - entry
        self.summary.setText(
            f"Valor financiado: {format_brl(financed)}   •   "
            f"{len(rows)}x de {format_brl(rows[0][2])}"
            + (f" (última parcela {format_brl(rows[-1][2])})" if rows[0][2] != rows[-1][2] else "")
        )
        self.preview.fill(
            [
                [
                    text_item(f"{numero}/{len(rows)}"),
                    date_item(vencimento),
                    money_item(valor),
                ]
                for numero, vencimento, valor in rows
            ]
        )

    def _save(self) -> None:
        client_id = self.client_combo.currentData()
        if client_id is None:
            warn(self, "Cliente", "Selecione o cliente do crediário.")
            return
        try:
            self.created_id = credit_service.create_credit(
                cliente_id=int(client_id),
                valor_total=parse_brl(self.total_edit.text()),
                entrada=parse_brl(self.entry_edit.text()),
                parcelas=self.count_spin.value(),
                primeiro_vencimento=self.first_due.get_date(),
                descricao=self.description_edit.text(),
                actor=self.ctx.user,
            )
        except (ValidationError, BusinessError, PermissionDenied, ValueError) as exc:
            warn(self, "Não foi possível criar", str(exc))
            return
        self.ctx.notify("Crediário criado com as parcelas geradas.")
        self.accept()


class CreditDetailDialog(QDialog):
    """Ficha do crediário com todas as parcelas e o registro de pagamento."""

    def __init__(self, ctx: AppContext, credit_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.credit_id = credit_id
        self.setWindowTitle(f"Crediário #{credit_id}")
        self.setMinimumSize(880, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        self.header = page_header("Crediário", "carregando...")
        layout.addWidget(self.header)

        self.identity = QLabel("")
        self.identity.setObjectName("Muted")
        layout.addWidget(self.identity)

        cards = QGridLayout()
        cards.setSpacing(12)
        self.card_compra = MetricCard("Compra", "cash", ACCENT)
        self.card_pago = MetricCard("Total pago", "check", GREEN)
        self.card_saldo = MetricCard("Saldo devedor", "list", YELLOW)
        self.card_vencido = MetricCard("Valor vencido", "alert", RED)
        for index, card in enumerate(
            (self.card_compra, self.card_pago, self.card_saldo, self.card_vencido)
        ):
            cards.addWidget(card, 0, index)
        layout.addLayout(cards)

        layout.addWidget(SectionTitle("Parcelas"))
        self.table = DataTable(
            ["Parcela", "Vencimento", "Valor", "Situação", "Pago em"],
            stretch=None,
            sortable=False,
        )
        self.table.setColumnWidth(0, 90)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.pay_button = primary_button("Marcar como pago", "check")
        self.pay_button.clicked.connect(self._mark_paid)
        self.undo_button = danger_button("Desfazer pagamento", "undo")
        self.undo_button.clicked.connect(self._undo)
        whats = button("WhatsApp", "whatsapp")
        whats.clicked.connect(self._whatsapp)
        close = button("Fechar", ghost=True)
        close.clicked.connect(self.accept)

        actions.addWidget(self.pay_button)
        actions.addWidget(self.undo_button)
        actions.addWidget(whats)
        actions.addStretch(1)
        actions.addWidget(close)
        layout.addLayout(actions)

        self.pay_button.setEnabled(ctx.can(Permission.PAYMENT_REGISTER))
        self.undo_button.setEnabled(ctx.can(Permission.PAYMENT_UNDO))
        if not ctx.can(Permission.PAYMENT_UNDO):
            self.undo_button.setToolTip("Somente o administrador pode desfazer pagamentos.")

        self.refresh()

    def refresh(self) -> None:
        try:
            detail = credit_service.get_detail(self.credit_id)
        except NotFoundError as exc:
            error(self, "Crediário", str(exc))
            self.reject()
            return

        self.detail = detail
        title = self.header.findChild(QLabel, "PageTitle")
        if title is not None:
            title.setText(detail.cliente)
        subtitle = self.header.findChild(QLabel, "PageSubtitle")
        if subtitle is not None:
            subtitle.setText(f"Crediário #{detail.id} — {detail.parcelas} parcelas")

        entrada = f"Entrada {format_brl(detail.entrada)}" if detail.entrada > ZERO else "Sem entrada"
        descricao = f"   •   {detail.descricao}" if detail.descricao else ""
        self.identity.setText(
            f"{detail.cpf}   •   {detail.telefone}   •   {entrada}   •   "
            f"Financiado {format_brl(detail.financiado)}{descricao}"
        )

        self.card_compra.set_value(format_brl(detail.valor_total))
        self.card_pago.set_value(format_brl(detail.total_pago), color=GREEN)
        self.card_saldo.set_value(format_brl(detail.saldo))
        self.card_vencido.set_value(
            format_brl(detail.vencido), color=RED if detail.vencido > ZERO else None
        )

        rows = []
        for item in detail.installments:
            label = item.status
            if item.status == "ATRASADO":
                label = f"ATRASADO — {item.dias_atraso} dias"
            rows.append(
                [
                    text_item(item.rotulo, key=item.id, bold=True),
                    date_item(item.vencimento),
                    money_item(item.valor),
                    status_item(label),
                    date_item(item.pago_em) if item.pago_em else text_item("—"),
                ]
            )
        self.table.fill(rows)
        if rows:
            self.table.selectRow(self._first_open_row(detail))

    @staticmethod
    def _first_open_row(detail: credit_service.CreditDetail) -> int:
        for index, item in enumerate(detail.installments):
            if not item.pago:
                return index
        return 0

    def _selected_installment(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            warn(self, "Parcela", "Selecione uma parcela na lista.")
            return None
        item = self.table.item(row, 0)
        return int(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _mark_paid(self) -> None:
        installment_id = self._selected_installment()
        if installment_id is None:
            return
        try:
            payment_service.mark_as_paid(installment_id, self.ctx.user)
        except (BusinessError, PermissionDenied) as exc:
            warn(self, "Pagamento", str(exc))
            return
        self.ctx.notify("Pagamento registrado.")
        self.refresh()

    def _undo(self) -> None:
        installment_id = self._selected_installment()
        if installment_id is None:
            return
        motivo, confirmado = QInputDialog.getText(
            self,
            "Estornar pagamento",
            "A parcela voltará para EM ABERTO ou ATRASADO conforme o vencimento e o\n"
            "recebimento sairá do caixa. O pagamento não é apagado: ele fica no\n"
            "histórico marcado como estornado.\n\nInforme o motivo do estorno:",
        )
        if not confirmado:
            return
        try:
            payment_service.reverse_payment(installment_id, motivo, self.ctx.user)
        except (BusinessError, PermissionDenied, ValidationError) as exc:
            warn(self, "Estorno", str(exc))
            return
        self.ctx.notify("Pagamento estornado e registrado na auditoria.")
        self.refresh()

    def _whatsapp(self) -> None:
        open_charge_whatsapp(
            self, self.detail.cliente_id, self.detail.cliente, self.detail.telefone
        )


class CreditsPage(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._term = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(page_header("Crediários", "Compras parceladas e seus saldos"))

        bar = QHBoxLayout()
        self.search = SearchBox("Pesquisar por cliente ou CPF")
        self.search.search.connect(self._on_search)
        bar.addWidget(self.search, 1)

        new_button = primary_button("Novo crediário", "plus")
        new_button.clicked.connect(lambda: self.new_credit())
        new_button.setEnabled(ctx.can(Permission.CREDIT_CREATE))
        bar.addWidget(new_button)
        layout.addLayout(bar)

        self.table = DataTable(
            [
                "Cliente",
                "CPF",
                "Compra",
                "Parcelas",
                "Saldo devedor",
                "Valor vencido",
            ],
            stretch=0,
            sortable=False,
        )
        self.table.doubleClicked.connect(lambda *_: self._open_selected())
        layout.addWidget(self.table, 1)

        footer = QHBoxLayout()
        open_button = button("Abrir crediário", "list")
        open_button.clicked.connect(self._open_selected)
        footer.addWidget(open_button)
        self.total_label = QLabel("")
        self.total_label.setObjectName("Muted")
        footer.addStretch(1)
        footer.addWidget(self.total_label)
        layout.addLayout(footer)

    def _on_search(self, term: str) -> None:
        self._term = term
        self.refresh()

    def refresh(self) -> None:
        rows = credit_service.list_credits(self._term)
        self.table.fill(
            [
                [
                    text_item(row.cliente, key=row.id),
                    text_item(row.cpf),
                    money_item(row.valor_total),
                    text_item(f"{row.pagas}/{row.parcelas} pagas"),
                    money_item(row.saldo),
                    money_item(row.vencido, color=RED if row.vencido > ZERO else TEXT_MUTED),
                ]
                for row in rows
            ]
        )
        saldo = sum((row.saldo for row in rows), ZERO)
        self.total_label.setText(
            f"{len(rows)} crediários   •   saldo total {format_brl(saldo)}"
        )

    def _open_selected(self) -> None:
        credit_id = self.table.selected_key()
        if credit_id is None:
            warn(self, "Crediário", "Selecione um crediário na lista.")
            return
        self.open_credit(credit_id)

    def open_credit(self, credit_id: int) -> None:
        dialog = CreditDetailDialog(self.ctx, credit_id, self)
        dialog.exec()
        self.refresh()

    def new_credit(self, client_id: int | None = None) -> None:
        dialog = NewCreditDialog(self.ctx, client_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.created_id:
            self.refresh()
            self.open_credit(dialog.created_id)
