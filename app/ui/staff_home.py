"""Terminal operacional do funcionário: poucas ações, botões grandes.

A tela oferece as ações do balcão e a lista dos últimos cadastros — **nada
mais**. Nenhum valor consolidado, nenhum indicador, nenhum totalizador, nem
zerado. O funcionário trabalha com o cliente à sua frente; a situação financeira
da loja não é assunto dele, e o componente que a mostraria não existe aqui.

Os cadastros recentes vêm de ``client_service.recent_clients``, que devolve
apenas nome, código, telefone e data: a ausência de dinheiro é garantida no
serviço, não por uma coluna escondida na tabela.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.security.permissions import Permission
from app.services import client_service
from app.ui import icons
from app.ui.context import AppContext
from app.ui.widgets import DataTable, SectionTitle, empty_hint, text_item
from app.utils.dates import format_datetime_br

#: Rótulo, ícone, atalho e permissão de cada ação do balcão.
ACTIONS = (
    ("NOVO CADASTRO", "plus", "Ctrl+N", Permission.CLIENT_CREATE),
    ("BUSCAR CLIENTE", "search", "Ctrl+F", Permission.CLIENT_VIEW),
    ("REGISTRAR PAGAMENTO", "cash", "Ctrl+R", Permission.PAYMENT_REGISTER),
    ("GERAR BOLETO", "receipt", "Ctrl+B", Permission.CHARGE_ISSUE),
)

#: Quantos cadastros recentes cabem sem transformar a tela em relatório.
RECENT_LIMIT = 8


class BigActionButton(QPushButton):
    """Botão grande e legível, com o atalho num selo discreto no canto.

    O atalho era uma segunda linha do rótulo e disputava peso visual com o nome
    da ação. Num selo separado, o funcionário lê primeiro *o que o botão faz* —
    e quem usa teclado continua vendo a tecla, ali e na dica.
    """

    def __init__(self, label: str, icon_name: str, shortcut: str) -> None:
        super().__init__(label)
        self.setObjectName("BigAction")
        self.setIcon(icons.icon(icon_name, "#ffffff", 28))
        self.setIconSize(QSize(28, 28))
        self.setMinimumHeight(112)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setShortcut(QKeySequence(shortcut))
        self.setToolTip(f"{label} ({shortcut})")

        self.hint = QLabel(shortcut, self)
        self.hint.setObjectName("BigActionHint")
        # Sem isto, o clique sobre o selo não chegaria ao botão.
        self.hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def resizeEvent(self, event) -> None:  # noqa: ANN001, N802
        """Mantém o selo ancorado no canto inferior direito."""
        super().resizeEvent(event)
        self.hint.adjustSize()
        self.hint.move(
            self.width() - self.hint.width() - 22,
            self.height() - self.hint.height() - 16,
        )


class StaffHomePage(QWidget):
    """Tela inicial do funcionário."""

    new_client = Signal()
    search_client = Signal()
    register_payment = Signal()
    issue_charge = Signal()
    #: Duplo clique em um cadastro recente abre a ficha daquele cliente.
    open_client = Signal(int)

    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

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
            self.search_client,
            self.register_payment,
            self.issue_charge,
        )
        for posicao, ((label, icon_name, shortcut, permissao), sinal) in enumerate(
            zip(ACTIONS, sinais)
        ):
            botao = BigActionButton(label, icon_name, shortcut)
            botao.setEnabled(ctx.can(permissao))
            botao.clicked.connect(sinal.emit)
            grid.addWidget(botao, posicao // 2, posicao % 2)
        layout.addLayout(grid)

        layout.addWidget(SectionTitle("Cadastros recentes"))
        self.table = DataTable(
            ["Código", "Nome", "Telefone", "Cadastrado em"], stretch=1, sortable=False
        )
        self.table.setMaximumHeight(230)
        self.table.doubleClicked.connect(self._open_selected)
        layout.addWidget(self.table)

        self.aviso = empty_hint(
            "Precisa de algo além destas ações? Fale com o administrador."
        )
        layout.addWidget(self.aviso)
        layout.addStretch(1)

        self.refresh()

    def _open_selected(self) -> None:
        client_id = self.table.selected_key()
        if client_id is not None:
            self.open_client.emit(int(client_id))

    def refresh(self) -> None:
        """Recarrega apenas os cadastros recentes — a tela não tem mais dados."""
        if not self.ctx.can(Permission.CLIENT_VIEW):
            self.table.fill([])
            return
        linhas = client_service.recent_clients(RECENT_LIMIT, actor=self.ctx.user)
        self.table.fill(
            [
                [
                    text_item(row.codigo, key=row.id, bold=True),
                    text_item(row.nome),
                    text_item(row.telefone),
                    text_item(
                        format_datetime_br(row.cadastrado_em) if row.cadastrado_em else "—"
                    ),
                ]
                for row in linhas
            ]
        )
