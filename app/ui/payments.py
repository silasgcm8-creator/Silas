"""Recebimentos: tudo que entrou no caixa, com filtros por período."""

from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.config import settings
from app.services import payment_service, report_service
from app.ui.context import AppContext
from app.ui.theme import GREEN
from app.ui.widgets import (
    DataTable,
    DateEdit,
    SearchBox,
    button,
    date_item,
    error,
    field_label,
    info,
    money_item,
    page_header,
    text_item,
)
from app.utils.dates import format_br, month_bounds, week_bounds
from app.utils.money import ZERO, format_brl

PERIODS = [
    ("Hoje", "hoje"),
    ("Esta semana", "semana"),
    ("Este mês", "mes"),
    ("Período personalizado", "personalizado"),
]


class PaymentsPage(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._term = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(page_header("Recebimentos", "Pagamentos registrados no sistema"))

        bar = QHBoxLayout()
        bar.addWidget(field_label("PERÍODO"))
        self.period_combo = QComboBox()
        self.period_combo.setMinimumHeight(38)
        for label, value in PERIODS:
            self.period_combo.addItem(label, value)
        self.period_combo.setCurrentIndex(2)
        self.period_combo.currentIndexChanged.connect(lambda *_: self._period_changed())
        bar.addWidget(self.period_combo)

        self.start_edit = DateEdit(month_bounds()[0])
        self.end_edit = DateEdit(month_bounds()[1])
        self.start_edit.dateChanged.connect(lambda _: self.refresh())
        self.end_edit.dateChanged.connect(lambda _: self.refresh())
        bar.addWidget(self.start_edit)
        bar.addWidget(QLabel("até"))
        bar.addWidget(self.end_edit)

        self.search = SearchBox("Filtrar por cliente ou CPF")
        self.search.search.connect(self._on_search)
        bar.addWidget(self.search, 1)

        export_button = button("Exportar CSV", "download")
        export_button.clicked.connect(lambda *_: self._export())
        bar.addWidget(export_button)
        layout.addLayout(bar)

        self.table = DataTable(
            ["Data", "Cliente", "CPF", "Parcela", "Valor", "Crediário", "Usuário"],
            stretch=1,
            sortable=False,
        )
        layout.addWidget(self.table, 1)

        self.total_label = QLabel("")
        self.total_label.setObjectName("CardValue")
        footer = QHBoxLayout()
        footer.addWidget(field_label("TOTAL RECEBIDO NO PERÍODO"))
        footer.addWidget(self.total_label)
        footer.addStretch(1)
        layout.addLayout(footer)

        self._period_changed()

    def _on_search(self, term: str) -> None:
        self._term = term
        self.refresh()

    def _period_changed(self) -> None:
        mode = self.period_combo.currentData()
        custom = mode == "personalizado"
        self.start_edit.setEnabled(custom)
        self.end_edit.setEnabled(custom)
        if mode == "hoje":
            start = end = date.today()
        elif mode == "semana":
            start, end = week_bounds()
        elif mode == "mes":
            start, end = month_bounds()
        else:
            self.refresh()
            return
        for widget, value in ((self.start_edit, start), (self.end_edit, end)):
            widget.blockSignals(True)
            widget.set_date(value)
            widget.blockSignals(False)
        self.refresh()

    def range(self) -> tuple[date, date]:
        start = self.start_edit.get_date()
        end = self.end_edit.get_date()
        return (start, end) if start <= end else (end, start)

    def refresh(self) -> None:
        start, end = self.range()
        rows = payment_service.list_payments(start, end, self._term)
        self.table.fill(
            [
                [
                    date_item(row.data, key=row.id),
                    text_item(row.cliente),
                    text_item(row.cpf),
                    text_item(row.parcela),
                    money_item(row.valor, color=GREEN),
                    text_item(f"#{row.crediario_id}"),
                    text_item(row.usuario),
                ]
                for row in rows
            ]
        )
        total = sum((row.valor for row in rows), ZERO)
        self.total_label.setText(format_brl(total))
        self.total_label.setStyleSheet(f"color: {GREEN};")

    def _export(self) -> None:
        start, end = self.range()
        suggestion = settings.base_dir / (
            f"Recebimentos_{start.isoformat()}_a_{end.isoformat()}.csv"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar recebimentos", str(suggestion), "Planilha CSV (*.csv)"
        )
        if not path:
            return
        try:
            report_service.export_payments(path, start, end, "csv")
        except Exception as exc:  # noqa: BLE001 - feedback direto ao usuário
            error(self, "Exportação", f"Não foi possível exportar: {exc}")
            return
        info(
            self,
            "Exportação concluída",
            f"Arquivo gerado para o período de {format_br(start)} a {format_br(end)}.",
        )
