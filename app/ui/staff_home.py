"""Terminal operacional do funcionário: poucas ações, botões grandes.

O funcionário não precisa enxergar a complexidade administrativa. Esta tela
oferece as quatro ações do balcão em botões grandes, com atalhos de teclado, e
mostra apenas o que ajuda o atendimento.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.security.permissions import Permission
from app.services import payment_service, report_service
from app.ui import icons
from app.ui.context import AppContext
from app.ui.theme import ACCENT, TEXT_MUTED
from app.ui.widgets import Card, empty_hint
from app.utils.dates import today as _hoje
from app.utils.money import format_brl

#: Rótulo, ícone, atalho e permissão de cada ação do balcão.
ACTIONS = (
    ("NOVO CLIENTE", "plus", "Ctrl+N", Permission.CLIENT_CREATE),
    ("REGISTRAR PAGAMENTO", "cash", "Ctrl+R", Permission.PAYMENT_REGISTER),
    ("PESQUISAR CLIENTE", "search", "Ctrl+F", Permission.CLIENT_VIEW),
    ("COMPROVANTES", "receipt", "Ctrl+P", Permission.RECEIPT_ISSUE),
)


class BigActionButton(QPushButton):
    """Botão grande e legível, com o atalho visível no próprio botão."""

    def __init__(self, label: str, icon_name: str, shortcut: str) -> None:
        super().__init__(f"{label}\n{shortcut}")
        self.setObjectName("BigAction")
        self.setIcon(icons.icon(icon_name, "#ffffff", 26))
        self.setMinimumHeight(104)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setShortcut(QKeySequence(shortcut))
        # O atalho fica também na dica, para quem navega por teclado.
        self.setToolTip(f"{label} ({shortcut})")


class StaffHomePage(QWidget):
    """Tela inicial do funcionário."""

    new_client = Signal()
    register_payment = Signal()
    search_client = Signal()
    receipts = Signal()

    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        saudacao = QVBoxLayout()
        saudacao.setSpacing(2)
        titulo = QLabel(f"Olá, {ctx.user.nome.split(' ')[0]}")
        titulo.setStyleSheet("font-size: 24px; font-weight: 700;")
        sub = QLabel("Escolha a ação desejada. Os atalhos do teclado também funcionam.")
        sub.setObjectName("Muted")
        saudacao.addWidget(titulo)
        saudacao.addWidget(sub)
        layout.addLayout(saudacao)

        grid = QGridLayout()
        grid.setSpacing(14)
        sinais = (
            self.new_client,
            self.register_payment,
            self.search_client,
            self.receipts,
        )
        for posicao, ((label, icon_name, shortcut, permissao), sinal) in enumerate(
            zip(ACTIONS, sinais)
        ):
            botao = BigActionButton(label, icon_name, shortcut)
            botao.setEnabled(ctx.can(permissao))
            botao.clicked.connect(sinal.emit)
            grid.addWidget(botao, posicao // 2, posicao % 2)
        layout.addLayout(grid)

        self.resumo = Card()
        titulo_resumo = QLabel("ATENDIMENTO DE HOJE")
        titulo_resumo.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; letter-spacing: 0.08em; font-weight: 600;"
        )
        self.resumo.body.addWidget(titulo_resumo)
        self.resumo_linha = QHBoxLayout()
        self.resumo_linha.setSpacing(28)
        self.resumo.body.addLayout(self.resumo_linha)
        layout.addWidget(self.resumo)

        self.aviso = empty_hint(
            "Precisa de algo além destas ações? Fale com o administrador."
        )
        layout.addWidget(self.aviso)
        layout.addStretch(1)

        self.refresh()

    def _metric(self, rotulo: str, valor: str) -> QWidget:
        caixa = QWidget()
        coluna = QVBoxLayout(caixa)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(2)
        titulo = QLabel(rotulo.upper())
        titulo.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; letter-spacing: 0.06em;"
        )
        numero = QLabel(valor)
        numero.setStyleSheet(f"color: {ACCENT}; font-size: 20px; font-weight: 700;")
        coluna.addWidget(titulo)
        coluna.addWidget(numero)
        return caixa

    def refresh(self) -> None:
        """Só indicadores do próprio atendimento — nada administrativo."""
        while self.resumo_linha.count():
            item = self.resumo_linha.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        painel = report_service.dashboard()
        self.resumo_linha.addWidget(
            self._metric("Recebido hoje", format_brl(painel.recebido_hoje))
        )
        self.resumo_linha.addWidget(
            self._metric("Pagamentos hoje", str(len(payment_service.list_payments(_hoje(), _hoje()))))
        )
        self.resumo_linha.addWidget(
            self._metric("Parcelas vencendo hoje", str(painel.parcelas_vencendo_hoje))
        )
        self.resumo_linha.addStretch(1)
