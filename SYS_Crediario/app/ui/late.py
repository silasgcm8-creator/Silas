"""Tela de atrasados: quem realmente possui valores vencidos."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.security.permissions import Permission
from app.services import report_service
from app.ui.context import AppContext
from app.ui.credits import open_charge_whatsapp
from app.ui.theme import RED
from app.ui.widgets import (
    DataTable,
    button,
    date_item,
    field_label,
    money_item,
    number_item,
    page_header,
    primary_button,
    text_item,
    warn,
)
from app.utils.money import ZERO, format_brl

ORDERS = [
    ("Maior valor vencido", "maior_valor_vencido"),
    ("Maior saldo devedor", "maior_saldo"),
    ("Maior atraso", "maior_atraso"),
    ("Vencimento mais antigo", "vencimento_antigo"),
    ("Nome do cliente", "nome"),
]


class LatePage(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._rows: list[report_service.LateRow] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(
            page_header("Atrasados", "Somente clientes com parcelas vencidas")
        )

        bar = QHBoxLayout()
        bar.addWidget(field_label("ORDENAR POR"))
        self.order_combo = QComboBox()
        self.order_combo.setMinimumHeight(38)
        for label, value in ORDERS:
            self.order_combo.addItem(label, value)
        self.order_combo.currentIndexChanged.connect(lambda _: self.refresh())
        bar.addWidget(self.order_combo)
        bar.addStretch(1)
        self.summary = QLabel("")
        self.summary.setObjectName("Muted")
        bar.addWidget(self.summary)
        layout.addLayout(bar)

        self.table = DataTable(
            [
                "Cliente",
                "CPF",
                "Telefone",
                "Valor vencido",
                "Saldo total",
                "Parcelas atrasadas",
                "Vencimento mais antigo",
                "Dias em atraso",
            ],
            stretch=0,
            sortable=False,
        )
        self.table.doubleClicked.connect(lambda *_: self._open_client())
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        open_button = primary_button("Abrir ficha do cliente", "users")
        open_button.clicked.connect(self._open_client)
        whats = button("WhatsApp", "whatsapp")
        whats.clicked.connect(self._whatsapp)
        whats.setEnabled(ctx.can(Permission.WHATSAPP))
        actions.addWidget(open_button)
        actions.addWidget(whats)
        actions.addStretch(1)
        layout.addLayout(actions)

    def refresh(self) -> None:
        order = self.order_combo.currentData() or "maior_valor_vencido"
        self._rows = report_service.late_clients(order)
        self.table.fill(
            [
                [
                    text_item(row.cliente, key=row.cliente_id),
                    text_item(row.cpf),
                    text_item(row.telefone),
                    money_item(row.vencido, color=RED),
                    money_item(row.saldo),
                    number_item(row.parcelas_vencidas, color=RED),
                    date_item(row.vencimento_antigo),
                    number_item(row.dias_atraso, color=RED),
                ]
                for row in self._rows
            ]
        )
        total = sum((row.vencido for row in self._rows), ZERO)
        self.summary.setText(
            f"{len(self._rows)} clientes em atraso   •   total vencido {format_brl(total)}"
        )
        if self._rows:
            self.table.selectRow(0)

    def _current(self) -> report_service.LateRow | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._rows):
            warn(self, "Atrasados", "Selecione um cliente na lista.")
            return None
        client_id = self.table.selected_key()
        for item in self._rows:
            if item.cliente_id == client_id:
                return item
        return self._rows[row]

    def _open_client(self) -> None:
        row = self._current()
        if row is None:
            return
        from app.ui.clients import ClientDetailDialog

        ClientDetailDialog(self.ctx, row.cliente_id, self).exec()
        self.refresh()

    def _whatsapp(self) -> None:
        row = self._current()
        if row is None:
            return
        open_charge_whatsapp(self, row.cliente_id, row.cliente, row.telefone)
