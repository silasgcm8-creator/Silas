"""Tela operacional REGISTRAR PAGAMENTO: o caixa do balcão, e nada além.

O caminho é o da operação:

    BUSCAR CLIENTE → IDENTIFICAR PARCELA → REGISTRAR → CONFIRMAR → COMPROVANTE

A tela mostra só o indispensável para receber: a parcela, o valor, a data, a
forma de pagamento e uma observação opcional. Não é extrato — não traz saldo do
cliente, histórico de compras, atraso nem totalizador de caixa.

O valor é o da parcela e não é editável: o sistema baixa parcelas inteiras. Um
recebimento parcial mudaria a semântica do crediário e precisa de decisão do
dono, não de um campo aberto no balcão.
"""

from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.status import PaymentMethod
from app.security.permissions import Permission, PermissionDenied
from app.services import client_service, payment_service, receipt_service
from app.services.errors import BusinessError, NotFoundError, ValidationError
from app.ui.context import AppContext
from app.ui.theme import TEXT_MUTED
from app.ui.widgets import (
    Card,
    DataTable,
    DateEdit,
    SearchBox,
    SectionTitle,
    button,
    confirm,
    date_item,
    empty_hint,
    error,
    field_label,
    money_item,
    open_file,
    page_header,
    primary_button,
    text_item,
    warn,
)
from app.utils.money import format_brl

#: Quantos clientes a busca mostra antes de pedir um termo melhor.
SEARCH_LIMIT = 30


class ReceivePaymentPage(QWidget):
    """Recebimento em cinco passos, sem sair da tela."""

    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._client_id: int | None = None
        self._client_name = ""
        self._last_payment: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(
            page_header(
                "Registrar pagamento",
                "Busque o cliente, escolha a parcela e confirme o recebimento",
            )
        )

        # ---- passo 1: cliente ----------------------------------------
        busca = Card()
        busca.body.addWidget(field_label("1. CLIENTE"))
        self.search = SearchBox("Nome, CPF, telefone ou código do cadastro")
        self.search.search.connect(self._search_clients)
        busca.body.addWidget(self.search)

        self.clients_table = DataTable(
            ["Código", "Nome", "CPF", "Telefone"], stretch=1, sortable=False
        )
        self.clients_table.setMaximumHeight(150)
        self.clients_table.doubleClicked.connect(lambda *_: self._select_client())
        busca.body.addWidget(self.clients_table)

        escolher = button("Selecionar cliente", "users")
        escolher.clicked.connect(self._select_client)
        linha = QHBoxLayout()
        linha.addWidget(escolher)
        linha.addStretch(1)
        busca.body.addLayout(linha)
        layout.addWidget(busca)

        # ---- passo 2: parcela ----------------------------------------
        layout.addWidget(SectionTitle("2. Parcela recebida"))
        self.chosen = QLabel("Nenhum cliente selecionado.")
        self.chosen.setStyleSheet(f"color: {TEXT_MUTED};")
        layout.addWidget(self.chosen)

        self.installments_table = DataTable(
            ["Crediário", "Parcela", "Vencimento", "Valor", "Documento"],
            stretch=1,
            sortable=False,
        )
        self.installments_table.itemSelectionChanged.connect(self._show_amount)
        layout.addWidget(self.installments_table, 1)

        # ---- passo 3: dados do recebimento ---------------------------
        dados = Card()
        dados.body.addWidget(field_label("3. DADOS DO RECEBIMENTO"))
        form = QFormLayout()
        form.setSpacing(10)

        self.amount_label = QLabel("—")
        self.amount_label.setObjectName("CardValue")
        form.addRow(field_label("VALOR RECEBIDO"), self.amount_label)

        self.date_edit = DateEdit(date.today())
        form.addRow(field_label("DATA"), self.date_edit)

        self.method_combo = QComboBox()
        self.method_combo.setMinimumHeight(38)
        for metodo in PaymentMethod:
            self.method_combo.addItem(metodo.label, metodo.value)
        form.addRow(field_label("FORMA DE PAGAMENTO"), self.method_combo)

        self.note_edit = QLineEdit()
        self.note_edit.setMinimumHeight(38)
        self.note_edit.setMaxLength(300)
        self.note_edit.setPlaceholderText("Observação do caixa (opcional)")
        form.addRow(field_label("OBSERVAÇÃO"), self.note_edit)
        dados.body.addLayout(form)
        layout.addWidget(dados)

        # ---- passos 4 e 5: confirmar e comprovante -------------------
        acoes = QHBoxLayout()
        self.confirm_button = primary_button("Registrar pagamento", "check")
        self.confirm_button.clicked.connect(self._register)
        self.confirm_button.setEnabled(False)
        self.receipt_button = button("Comprovante", "receipt")
        self.receipt_button.clicked.connect(self._receipt)
        self.receipt_button.setEnabled(False)
        acoes.addWidget(self.confirm_button)
        acoes.addWidget(self.receipt_button)
        acoes.addStretch(1)
        layout.addLayout(acoes)

        self.result = empty_hint(
            "O valor é o da parcela escolhida. Confirme para dar baixa e emitir "
            "o comprovante."
        )
        layout.addWidget(self.result)

        self._search_clients("")

    # ---- passo 1 -----------------------------------------------------

    def _search_clients(self, term: str = "") -> None:
        rows = client_service.list_clients(term, limit=SEARCH_LIMIT, actor=self.ctx.user)
        self.clients_table.fill(
            [
                [
                    text_item(client_service.client_code(row.id), key=row.id, bold=True),
                    text_item(row.nome),
                    text_item(row.cpf),
                    text_item(row.telefone),
                ]
                for row in rows
            ]
        )
        if rows:
            self.clients_table.selectRow(0)

    def _select_client(self) -> None:
        client_id = self.clients_table.selected_key()
        if client_id is None:
            warn(self, "Cliente", "Escolha um cliente na lista.")
            return
        nome = self.clients_table.item(self.clients_table.currentRow(), 1)
        self._client_id = int(client_id)
        self._client_name = nome.text() if nome is not None else ""
        self._last_payment = None
        self.receipt_button.setEnabled(False)
        self.refresh()

    # ---- passo 2 -----------------------------------------------------

    def refresh(self) -> None:
        """Recarrega as parcelas em aberto do cliente escolhido (só dele)."""
        if self._client_id is None:
            self.installments_table.fill([])
            self.confirm_button.setEnabled(False)
            return

        self.chosen.setText(
            f"Cliente: {self._client_name}   •   "
            f"código {client_service.client_code(self._client_id)}"
        )
        self.chosen.setStyleSheet("font-weight: 600;")

        try:
            self._rows = payment_service.payable_for_client(
                self._client_id, self.ctx.user
            )
        except PermissionDenied as exc:
            warn(self, "Pagamento", str(exc))
            return

        self.installments_table.fill(
            [
                [
                    text_item(f"{row.crediario_id:06d}", key=row.parcela_id),
                    text_item(row.parcela, bold=True),
                    date_item(row.vencimento),
                    money_item(row.valor),
                    text_item(row.documento or "—"),
                ]
                for row in self._rows
            ]
        )
        if self._rows:
            self.installments_table.selectRow(0)
            self.result.setText(
                "Confira o valor, escolha a forma de pagamento e registre."
            )
        else:
            self.confirm_button.setEnabled(False)
            self.amount_label.setText("—")
            self.result.setText(
                f"{self._client_name} não tem parcelas em aberto para receber."
            )

    def _selected(self) -> payment_service.PayableRow | None:
        parcela_id = self.installments_table.selected_key()
        if parcela_id is None:
            return None
        for row in getattr(self, "_rows", []):
            if row.parcela_id == int(parcela_id):
                return row
        return None

    def _show_amount(self) -> None:
        """O valor exibido é sempre o da parcela selecionada — nunca digitado."""
        row = self._selected()
        self.amount_label.setText(format_brl(row.valor) if row else "—")
        self.confirm_button.setEnabled(row is not None)

    # ---- passos 4 e 5 ------------------------------------------------

    def _register(self) -> None:
        row = self._selected()
        if row is None:
            warn(self, "Parcela", "Escolha a parcela que está sendo recebida.")
            return

        data = self.date_edit.get_date()
        forma_rotulo = self.method_combo.currentText()
        if not confirm(
            self,
            "Confirmar recebimento?",
            f"Cliente: {self._client_name}\n"
            f"Parcela: {row.parcela}\n"
            f"Valor: {format_brl(row.valor)}\n"
            f"Data: {data.strftime('%d/%m/%Y')}\n"
            f"Forma de pagamento: {forma_rotulo}\n\n"
            "Confirmar a baixa desta parcela?",
        ):
            return

        try:
            self._last_payment = payment_service.mark_as_paid(
                row.parcela_id,
                actor=self.ctx.user,
                payment_date=data,
                forma_pagamento=self.method_combo.currentData(),
                documento_id=row.documento_id,
                observacao=self.note_edit.text(),
            )
        except (BusinessError, NotFoundError, ValidationError, PermissionDenied) as exc:
            warn(self, "Pagamento", str(exc))
            return

        self.note_edit.clear()
        self.receipt_button.setEnabled(True)
        self.ctx.notify(f"Pagamento registrado ({forma_rotulo}).")
        # A recarga vem antes da mensagem: `refresh` também escreve no rodapé, e
        # o funcionário precisa ler a confirmação da operação que acabou de fazer.
        self.refresh()
        self.result.setText(
            f"Parcela {row.parcela} baixada — {format_brl(row.valor)} em "
            f"{forma_rotulo}. Use Comprovante para entregar ao cliente."
        )

    def _receipt(self) -> None:
        if self._last_payment is None:
            warn(self, "Comprovante", "Registre um pagamento antes de imprimir.")
            return
        try:
            caminho, _ = receipt_service.issue(self._last_payment, actor=self.ctx.user)
        except (NotFoundError, PermissionDenied) as exc:
            warn(self, "Comprovante", str(exc))
            return
        except OSError as exc:
            error(self, "Comprovante", f"Não foi possível gravar o PDF: {exc}")
            return
        self.result.setText(f"Comprovante gerado em {caminho}.")
        open_file(caminho)
