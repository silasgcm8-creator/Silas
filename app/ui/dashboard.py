"""Tela inicial: indicadores, próximos vencimentos e atrasos recentes."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from app.services import report_service
from app.ui.context import AppContext
from app.ui.theme import ACCENT, GREEN, PURPLE, RED, YELLOW
from app.ui.widgets import (
    Card,
    DataTable,
    MetricCard,
    SectionTitle,
    date_item,
    money_item,
    page_header,
    text_item,
)
from app.utils.dates import days_late
from app.utils.money import format_brl


class DashboardPage(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(
            page_header("Início", "Situação do crediário em tempo real")
        )

        grid = QGridLayout()
        grid.setSpacing(12)
        self.card_receber = MetricCard("Total a receber", "cash", ACCENT)
        self.card_vencido = MetricCard("Total vencido", "alert", RED)
        self.card_recebido = MetricCard("Recebido no mês", "check", GREEN)
        self.card_clientes = MetricCard("Clientes em atraso", "users", YELLOW)
        self.card_hoje = MetricCard("Vencendo hoje", "list", PURPLE)
        self.card_parcelas = MetricCard("Parcelas vencidas", "alert", RED)

        cards = [
            self.card_receber,
            self.card_vencido,
            self.card_recebido,
            self.card_clientes,
            self.card_hoje,
            self.card_parcelas,
        ]
        for index, card in enumerate(cards):
            grid.addWidget(card, index // 3, index % 3)
        layout.addLayout(grid)

        panels = QHBoxLayout()
        panels.setSpacing(12)

        upcoming_card = Card()
        upcoming_card.body.addWidget(SectionTitle("Próximos vencimentos"))
        self.upcoming_table = DataTable(
            ["Cliente", "CPF", "Parcela", "Vencimento", "Valor"], stretch=0, sortable=False
        )
        upcoming_card.body.addWidget(self.upcoming_table)
        panels.addWidget(upcoming_card, 3)

        late_card = Card()
        late_card.body.addWidget(SectionTitle("Atrasos recentes"))
        self.late_table = DataTable(
            ["Cliente", "Vencimento", "Dias", "Valor"], stretch=0, sortable=False
        )
        late_card.body.addWidget(self.late_table)
        panels.addWidget(late_card, 2)

        layout.addLayout(panels, 1)

    def refresh(self) -> None:
        data = report_service.dashboard(self.ctx.user)
        self.card_receber.set_value(format_brl(data.total_a_receber))
        self.card_vencido.set_value(
            format_brl(data.total_vencido),
            color=RED if data.total_vencido > 0 else None,
        )
        self.card_recebido.set_value(format_brl(data.recebido_no_mes), color=GREEN)
        self.card_clientes.set_value(str(data.clientes_em_atraso))
        self.card_hoje.set_value(
            str(data.parcelas_vencendo_hoje),
            hint=f"{format_brl(data.valor_vencendo_hoje)} previstos para hoje",
        )
        self.card_parcelas.set_value(
            str(data.parcelas_vencidas),
            color=RED if data.parcelas_vencidas else None,
        )

        rows = []
        for item in report_service.upcoming(self.ctx.user, limit=12):
            rows.append(
                [
                    text_item(item.cliente, key=item.crediario_id),
                    text_item(item.cpf),
                    text_item(item.parcela),
                    date_item(item.vencimento),
                    money_item(item.valor),
                ]
            )
        self.upcoming_table.fill(rows)

        late_rows = []
        for item in report_service.recent_late(self.ctx.user, limit=12):
            late_rows.append(
                [
                    text_item(item.cliente, key=item.crediario_id),
                    date_item(item.vencimento),
                    text_item(f"{days_late(item.vencimento)}"),
                    money_item(item.valor, color=RED),
                ]
            )
        self.late_table.fill(late_rows)
        for table in (self.upcoming_table, self.late_table):
            table.setTextElideMode(Qt.TextElideMode.ElideRight)
