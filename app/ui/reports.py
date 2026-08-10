"""Relatórios por período com exportação."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.config import settings
from app.services import payment_service, report_service
from app.ui.context import AppContext
from app.ui.theme import ACCENT, GREEN, PURPLE, RED, YELLOW
from app.ui.widgets import (
    Card,
    DataTable,
    DateEdit,
    MetricCard,
    SectionTitle,
    button,
    date_item,
    error,
    field_label,
    info,
    money_item,
    page_header,
    primary_button,
    text_item,
)
from app.utils.dates import format_br, format_datetime_br, month_bounds
from app.utils.export import available_formats
from app.utils.money import format_brl


class ReportsPage(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(page_header("Relatórios", "Resultados do período escolhido"))

        bar = QHBoxLayout()
        bar.addWidget(field_label("DE"))
        start, end = month_bounds()
        self.start_edit = DateEdit(start)
        bar.addWidget(self.start_edit)
        bar.addWidget(field_label("ATÉ"))
        self.end_edit = DateEdit(end)
        bar.addWidget(self.end_edit)

        generate = primary_button("Gerar relatório", "chart")
        generate.clicked.connect(lambda *_: self.refresh())
        bar.addWidget(generate)
        bar.addStretch(1)

        bar.addWidget(field_label("FORMATO"))
        self.format_combo = QComboBox()
        self.format_combo.setMinimumHeight(38)
        for fmt in available_formats():
            self.format_combo.addItem(fmt.upper(), fmt)
        bar.addWidget(self.format_combo)

        export_summary = button("Exportar resumo", "download")
        export_summary.clicked.connect(lambda *_: self._export_summary())
        bar.addWidget(export_summary)

        export_open = button("Exportar em aberto", "download")
        export_open.clicked.connect(lambda *_: self._export_receivables())
        bar.addWidget(export_open)

        export_reversals = button("Exportar estornos", "download")
        export_reversals.clicked.connect(lambda *_: self._export_reversals())
        bar.addWidget(export_reversals)
        layout.addLayout(bar)

        cards = QGridLayout()
        cards.setSpacing(12)
        self.card_vendido = MetricCard("Total vendido", "cash", ACCENT)
        self.card_recebido = MetricCard("Total recebido", "check", GREEN)
        self.card_receber = MetricCard("Total a receber", "list", PURPLE)
        self.card_vencido = MetricCard("Total vencido", "alert", RED)
        self.card_ativos = MetricCard("Clientes ativos", "users", ACCENT)
        self.card_atraso = MetricCard("Clientes em atraso", "users", YELLOW)
        self.card_parcelas = MetricCard("Parcelas vencidas", "alert", RED)
        self.card_futuro = MetricCard("Vencimentos futuros", "chart", PURPLE)
        for index, card in enumerate(
            (
                self.card_vendido,
                self.card_recebido,
                self.card_receber,
                self.card_vencido,
                self.card_ativos,
                self.card_atraso,
                self.card_parcelas,
                self.card_futuro,
            )
        ):
            cards.addWidget(card, index // 4, index % 4)
        layout.addLayout(cards)

        detail = Card()
        detail.body.addWidget(SectionTitle("Vencimentos futuros"))
        self.table = DataTable(
            ["Cliente", "CPF", "Parcela", "Vencimento", "Valor"], stretch=0, sortable=False
        )
        detail.body.addWidget(self.table)
        layout.addWidget(detail, 1)

        # Estornos do período: conferência de caixa e trilha de auditoria.
        reversals = Card()
        cabecalho = QHBoxLayout()
        cabecalho.addWidget(SectionTitle("Estornos do período"))
        cabecalho.addStretch(1)
        cabecalho.addWidget(field_label("TOTAL ESTORNADO"))
        self.reversed_label = QLabel("—")
        self.reversed_label.setObjectName("CardValue")
        cabecalho.addWidget(self.reversed_label)
        reversals.body.addLayout(cabecalho)

        self.reversals_table = DataTable(
            [
                "Estornado em",
                "Cliente",
                "Parcela",
                "Valor",
                "Identificador",
                "Motivo",
                "Autorizado por",
            ],
            stretch=5,
            sortable=False,
        )
        reversals.body.addWidget(self.reversals_table)
        self.reversals_hint = QLabel("")
        self.reversals_hint.setObjectName("Muted")
        reversals.body.addWidget(self.reversals_hint)
        layout.addWidget(reversals, 1)

        self.footer = QLabel("")
        self.footer.setObjectName("Muted")
        layout.addWidget(self.footer)

        self.refresh()

    def range(self):  # noqa: ANN201
        start = self.start_edit.get_date()
        end = self.end_edit.get_date()
        return (start, end) if start <= end else (end, start)

    def refresh(self) -> None:
        start, end = self.range()
        data = report_service.report(self.ctx.user, start, end)
        self.card_vendido.set_value(format_brl(data.total_vendido))
        self.card_recebido.set_value(format_brl(data.total_recebido), color=GREEN)
        self.card_receber.set_value(format_brl(data.total_a_receber))
        self.card_vencido.set_value(format_brl(data.total_vencido), color=RED)
        self.card_ativos.set_value(str(data.clientes_ativos))
        self.card_atraso.set_value(str(data.clientes_em_atraso))
        self.card_parcelas.set_value(str(data.parcelas_vencidas))
        self.card_futuro.set_value(format_brl(data.vencimentos_futuros))

        self.table.fill(
            [
                [
                    text_item(row.cliente),
                    text_item(row.cpf),
                    text_item(row.parcela),
                    date_item(row.vencimento),
                    money_item(row.valor),
                ]
                for row in report_service.upcoming(self.ctx.user, limit=40)
            ]
        )
        self._refresh_reversals(start, end)
        self.footer.setText(
            f"Período analisado: {format_br(start)} a {format_br(end)}."
        )

    def _fmt(self) -> str:
        return str(self.format_combo.currentData() or "csv")

    def _ask_path(self, name: str) -> str:
        fmt = self._fmt()
        suggestion = settings.base_dir / f"{name}.{fmt}"
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar relatório", str(suggestion), f"Arquivo {fmt.upper()} (*.{fmt})"
        )
        return path

    def _refresh_reversals(self, start, end) -> None:  # noqa: ANN001
        estornos = payment_service.list_reversals(self.ctx.user, start, end)
        self.reversals_table.fill(
            [
                [
                    text_item(format_datetime_br(item.data), key=item.id),
                    text_item(item.cliente),
                    text_item(item.parcela),
                    money_item(item.valor, color=RED),
                    text_item(item.pagamento_codigo),
                    text_item(item.motivo),
                    text_item(item.usuario),
                ]
                for item in estornos
            ]
        )
        total = report_service.total_reversed(self.ctx.user, start, end)
        self.reversed_label.setText(format_brl(total))
        self.reversed_label.setStyleSheet(f"color: {RED};")
        self.reversals_hint.setText(
            "Nenhum estorno no período."
            if not estornos
            else f"{len(estornos)} estorno(s). O pagamento original continua no "
            "histórico, marcado como estornado."
        )

    def _export_reversals(self) -> None:
        start, end = self.range()
        fmt = self._fmt()
        path = self._ask_path(f"Estornos_{start.isoformat()}_a_{end.isoformat()}")
        if not path:
            return
        try:
            report_service.export_reversals(self.ctx.user, path, start, end, fmt)
        except Exception as exc:  # noqa: BLE001 - feedback direto ao usuário
            error(self, "Exportação", f"Não foi possível exportar: {exc}")
            return
        info(self, "Exportação concluída", f"Arquivo gerado:\n{path}")

    def _export_summary(self) -> None:
        start, end = self.range()
        path = self._ask_path(f"Relatorio_{start.isoformat()}_a_{end.isoformat()}")
        if not path:
            return
        try:
            report_service.export_report(
                self.ctx.user, path, report_service.report(self.ctx.user, start, end), self._fmt()
            )
        except Exception as exc:  # noqa: BLE001
            error(self, "Exportação", f"Não foi possível exportar: {exc}")
            return
        info(self, "Exportação concluída", "Resumo do período exportado com sucesso.")

    def _export_receivables(self) -> None:
        path = self._ask_path("Valores_em_aberto")
        if not path:
            return
        try:
            report_service.export_receivables(self.ctx.user, path, self._fmt())
        except Exception as exc:  # noqa: BLE001
            error(self, "Exportação", f"Não foi possível exportar: {exc}")
            return
        info(self, "Exportação concluída", "Parcelas em aberto exportadas com sucesso.")
