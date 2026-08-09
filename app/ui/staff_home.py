"""Terminal operacional do funcionário: poucas ações, botões grandes.

A tela oferece as ações do balcão e **nada mais**. Nenhum valor consolidado,
nenhum indicador, nenhum totalizador — nem zerado. O funcionário trabalha com o
cliente à sua frente; a situação financeira da loja não é assunto dele, e o
componente que a mostraria simplesmente não existe aqui.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.security.permissions import Permission
from app.ui import icons
from app.ui.context import AppContext
from app.ui.widgets import empty_hint

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

        self.aviso = empty_hint(
            "Precisa de algo além destas ações? Fale com o administrador."
        )
        layout.addWidget(self.aviso)
        layout.addStretch(1)

    def refresh(self) -> None:
        """Nada a atualizar: a tela não exibe dado nenhum, só ações."""
