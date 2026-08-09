"""Tela BOLETOS: histórico, filtros e ações dos documentos de cobrança."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.models.charge import (
    CHARGE_TYPE_LABELS,
    STATUS_CANCELLED,
    STATUS_LATE,
    STATUS_OPEN,
    STATUS_PAID,
    TYPE_BANK,
    TYPE_REGISTERED,
    TYPE_STORE,
)
from app.security.permissions import Permission, PermissionDenied
from app.services import bank_account_service, charge_service, receipt_service
from app.services.errors import BusinessError, NotFoundError, ValidationError
from app.ui.charge_dialogs import ReceivePaymentDialog
from app.ui.context import AppContext
from app.ui.theme import GREEN, RED, TEXT_MUTED, YELLOW
from app.ui.widgets import (
    DataTable,
    DateEdit,
    SearchBox,
    button,
    confirm,
    danger_button,
    date_item,
    field_label,
    money_item,
    open_file,
    page_header,
    primary_button,
    status_item,
    text_item,
    warn,
)
from app.utils.dates import format_br, month_bounds
from app.utils.money import ZERO, format_brl

#: Filtros rápidos da barra superior.
QUICK_FILTERS = (
    ("TODOS", ""),
    ("EM ABERTO", STATUS_OPEN),
    ("PAGOS", STATUS_PAID),
    ("ATRASADOS", STATUS_LATE),
    ("CANCELADOS", STATUS_CANCELLED),
)

STATUS_COLORS = {
    STATUS_PAID: GREEN,
    STATUS_OPEN: YELLOW,
    STATUS_LATE: RED,
    STATUS_CANCELLED: TEXT_MUTED,
}


class ChargesPage(QWidget):
    """Histórico de cobranças com filtros e as ações do balcão."""

    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._term = ""
        self._situacao = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(
            page_header("Boletos", "Documentos de cobrança emitidos pela loja")
        )

        # ---- filtros rápidos ----------------------------------------
        rapidos = QHBoxLayout()
        rapidos.setSpacing(8)
        self.quick_buttons: dict[str, QWidget] = {}
        for rotulo, valor in QUICK_FILTERS:
            botao = button(rotulo, ghost=True)
            botao.setCheckable(True)
            botao.clicked.connect(lambda _=False, v=valor: self._set_quick(v))
            rapidos.addWidget(botao)
            self.quick_buttons[valor] = botao
        rapidos.addStretch(1)
        layout.addLayout(rapidos)

        # ---- busca e filtros detalhados -----------------------------
        bar = QHBoxLayout()
        self.search = SearchBox("Nome, CPF, documento, crediário ou parcela")
        self.search.search.connect(self._on_search)
        bar.addWidget(self.search, 1)

        bar.addWidget(field_label("TIPO"))
        self.type_combo = QComboBox()
        self.type_combo.setMinimumHeight(38)
        self.type_combo.addItem("Todos", "")
        for tipo in (TYPE_STORE, TYPE_BANK, TYPE_REGISTERED):
            self.type_combo.addItem(CHARGE_TYPE_LABELS[tipo], tipo)
        self.type_combo.currentIndexChanged.connect(lambda *_: self.refresh())
        bar.addWidget(self.type_combo)

        bar.addWidget(field_label("CONTA"))
        self.account_combo = QComboBox()
        self.account_combo.setMinimumHeight(38)
        self.account_combo.addItem("Todas", None)
        for conta in bank_account_service.list_accounts(only_active=False):
            self.account_combo.addItem(conta.identificacao, conta.id)
        self.account_combo.currentIndexChanged.connect(lambda *_: self.refresh())
        bar.addWidget(self.account_combo)
        layout.addLayout(bar)

        periodo = QHBoxLayout()
        periodo.addWidget(field_label("PERÍODO POR"))
        self.date_field = QComboBox()
        self.date_field.setMinimumHeight(38)
        self.date_field.addItem("Emissão", False)
        self.date_field.addItem("Vencimento", True)
        self.date_field.currentIndexChanged.connect(lambda *_: self.refresh())
        periodo.addWidget(self.date_field)

        inicio, fim = month_bounds()
        self.start_edit = DateEdit(inicio)
        self.end_edit = DateEdit(fim)
        self.start_edit.dateChanged.connect(lambda *_: self.refresh())
        self.end_edit.dateChanged.connect(lambda *_: self.refresh())
        periodo.addWidget(self.start_edit)
        periodo.addWidget(QLabel("até"))
        periodo.addWidget(self.end_edit)
        periodo.addStretch(1)
        layout.addLayout(periodo)

        # ---- tabela -------------------------------------------------
        self.table = DataTable(
            [
                "Documento",
                "Cliente",
                "CPF",
                "Crediário",
                "Parcela",
                "Emissão",
                "Vencimento",
                "Valor",
                "Tipo de pagamento",
                "Situação",
            ],
            stretch=1,
            sortable=False,
        )
        self.table.doubleClicked.connect(lambda *_: self._reprint())
        layout.addWidget(self.table, 1)

        # ---- ações --------------------------------------------------
        acoes = QHBoxLayout()
        self.reprint_button = primary_button("Reimprimir / abrir PDF", "receipt")
        self.reprint_button.clicked.connect(self._reprint)
        self.reprint_button.setEnabled(ctx.can(Permission.CHARGE_ISSUE))

        self.receive_button = button("Receber pagamento", "cash")
        self.receive_button.clicked.connect(self._receive)
        self.receive_button.setEnabled(ctx.can(Permission.PAYMENT_REGISTER))

        self.receipt_button = button("Comprovante do pagamento", "check")
        self.receipt_button.clicked.connect(self._receipt)
        self.receipt_button.setEnabled(ctx.can(Permission.RECEIPT_ISSUE))

        self.history_button = button("Histórico", "list", ghost=True)
        self.history_button.clicked.connect(self._history)

        self.cancel_button = danger_button("Cancelar documento", "logout")
        self.cancel_button.clicked.connect(self._cancel)
        self.cancel_button.setEnabled(ctx.can(Permission.CHARGE_CANCEL))
        if not ctx.can(Permission.CHARGE_CANCEL):
            self.cancel_button.setToolTip(
                "Somente o administrador pode cancelar um documento."
            )

        for widget in (
            self.reprint_button,
            self.receive_button,
            self.receipt_button,
            self.history_button,
            self.cancel_button,
        ):
            acoes.addWidget(widget)
        acoes.addStretch(1)
        layout.addLayout(acoes)

        self.footer = QLabel("")
        self.footer.setObjectName("Muted")
        layout.addWidget(self.footer)

        self._set_quick("")

    # ---- filtros ----------------------------------------------------

    def _set_quick(self, situacao: str) -> None:
        self._situacao = situacao
        for valor, botao in self.quick_buttons.items():
            botao.setChecked(valor == situacao)
        self.refresh()

    def _on_search(self, term: str) -> None:
        self._term = term
        self.refresh()

    def range(self) -> tuple[date, date]:
        inicio = self.start_edit.get_date()
        fim = self.end_edit.get_date()
        return (inicio, fim) if inicio <= fim else (fim, inicio)

    def refresh(self) -> None:
        inicio, fim = self.range()
        linhas = charge_service.list_documents(
            term=self._term,
            situacao=self._situacao,
            tipo=self.type_combo.currentData() or "",
            conta_id=self.account_combo.currentData(),
            inicio=inicio,
            fim=fim,
            por_vencimento=bool(self.date_field.currentData()),
        )
        self.table.fill(
            [
                [
                    text_item(row.numero, key=row.id),
                    text_item(row.cliente),
                    text_item(row.cpf),
                    text_item(f"{row.crediario_id:06d}"),
                    text_item(row.parcela),
                    date_item(row.emissao),
                    date_item(row.vencimento),
                    money_item(row.valor),
                    text_item(row.tipo_label),
                    status_item(row.situacao),
                ]
                for row in linhas
            ]
        )
        total = sum((row.valor for row in linhas if not row.cancelado), ZERO)
        self.footer.setText(
            f"{len(linhas)} documento(s) — total não cancelado {format_brl(total)}. "
            "Dois cliques na linha reimprime o documento."
        )

    # ---- ações ------------------------------------------------------

    def _selected(self) -> charge_service.ChargeView | None:
        document_id = self.table.selected_key()
        if document_id is None:
            warn(self, "Boletos", "Selecione um documento na lista.")
            return None
        try:
            return charge_service.build(document_id)
        except NotFoundError as exc:
            warn(self, "Boletos", str(exc))
            return None

    def _reprint(self) -> None:
        view = self._selected()
        if view is None:
            return
        try:
            caminho, dados = charge_service.issue_pdf(view.id, actor=self.ctx.user)
        except (BusinessError, NotFoundError, PermissionDenied) as exc:
            warn(self, "Reimpressão", str(exc))
            return
        self.refresh()
        self.ctx.notify(f"Documento {dados.numero} gerado novamente.")
        if confirm(
            self,
            "Documento pronto",
            f"{dados.numero} — parcela {dados.parcela}\n"
            f"Valor: {format_brl(dados.valor_atualizado)}\n"
            f"Vencimento: {format_br(dados.vencimento)}\n\n"
            f"Arquivo:\n{caminho}\n\nAbrir agora para imprimir?",
        ):
            open_file(caminho)

    def _receive(self) -> None:
        view = self._selected()
        if view is None:
            return
        if view.situacao == STATUS_PAID:
            warn(self, "Receber pagamento", "Esta parcela já está paga.")
            return
        if view.situacao == STATUS_CANCELLED:
            warn(
                self,
                "Receber pagamento",
                "Documento cancelado. Emita uma nova cobrança para receber.",
            )
            return

        dialog = ReceivePaymentDialog(self.ctx, view, self)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.payment_id is None:
            self.refresh()
            return

        self.refresh()
        if confirm(
            self,
            "Pagamento registrado",
            "Imprimir o comprovante de pagamento agora?",
        ):
            self._issue_receipt(dialog.payment_id)

    def _receipt(self) -> None:
        """Comprovante do pagamento já registrado para o documento."""
        view = self._selected()
        if view is None:
            return
        if view.situacao != STATUS_PAID:
            warn(
                self,
                "Comprovante",
                "O comprovante fica disponível depois que o pagamento é registrado.",
            )
            return

        from app.database.connection import session_scope
        from app.repositories.payment_repository import PaymentRepository

        with session_scope() as session:
            pagamento = PaymentRepository(session).get_active_by_installment(
                view.parcela_id
            )
            payment_id = pagamento.id if pagamento else None
        if payment_id is None:
            warn(self, "Comprovante", "Recebimento não localizado para esta parcela.")
            return
        self._issue_receipt(payment_id)

    def _issue_receipt(self, payment_id: int) -> None:
        try:
            caminho, dados = receipt_service.issue(payment_id, actor=self.ctx.user)
        except (BusinessError, NotFoundError, PermissionDenied) as exc:
            warn(self, "Comprovante", str(exc))
            return
        self.ctx.notify(f"Comprovante {dados.codigo} gerado.")
        if confirm(
            self,
            "Comprovante gerado",
            f"Arquivo:\n{caminho}\n\nAbrir agora para imprimir?",
        ):
            open_file(caminho)

    def _cancel(self) -> None:
        view = self._selected()
        if view is None:
            return
        motivo, ok = QInputDialog.getText(
            self,
            "Cancelar documento",
            f"O documento {view.numero} deixará de valer. O registro permanece no\n"
            "histórico com o motivo.\n\nMotivo do cancelamento:",
        )
        if not ok:
            return
        try:
            charge_service.cancel(view.id, motivo, self.ctx.user)
        except (BusinessError, NotFoundError, PermissionDenied, ValidationError) as exc:
            warn(self, "Cancelamento", str(exc))
            return
        self.refresh()
        self.ctx.notify(f"Documento {view.numero} cancelado.")

    def _history(self) -> None:
        view = self._selected()
        if view is None:
            return
        eventos = charge_service.history(view.id)
        if not eventos:
            warn(self, "Histórico", "Nenhum evento registrado.")
            return
        texto = "\n".join(
            f"{evento.quando:%d/%m/%Y %H:%M} — {evento.evento}"
            + (f": {evento.detalhes}" if evento.detalhes else "")
            + f"  [{evento.usuario}]"
            for evento in eventos
        )
        from app.ui.widgets import info

        info(self, f"Histórico do documento {view.numero}", texto)
