"""Tela operacional GERAR BOLETO: um cliente, uma parcela, um documento.

O caminho é o do balcão, e só ele:

    BUSCAR CLIENTE → ESCOLHER A PARCELA → GERAR → IMPRIMIR

Nada de filtros, histórico, indicadores ou documentos de outros clientes. Até a
lista de parcelas vem de ``charge_service.issuable_for_client``, que só enxerga
o cliente escolhido e não devolve situação de atraso — o funcionário emite um
documento, não consulta inadimplência.

A tela completa de gestão de cobranças (filtros, histórico, cancelamento)
continua existindo em BOLETOS, para o administrador.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.security.permissions import Permission, PermissionDenied
from app.services import charge_service, client_service
from app.services.banking import IntegrationNotConfigured
from app.services.errors import BusinessError, NotFoundError, ValidationError
from app.ui.charge_dialogs import ChargeTypeDialog
from app.ui.context import AppContext
from app.ui.theme import TEXT_MUTED
from app.ui.widgets import (
    Card,
    DataTable,
    SearchBox,
    SectionTitle,
    button,
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

#: Quantos clientes a busca mostra antes de pedir um termo melhor.
SEARCH_LIMIT = 30


class IssueChargePage(QWidget):
    """Emissão de cobrança em quatro passos, sem sair da tela."""

    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._client_id: int | None = None
        self._client_name = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(
            page_header(
                "Gerar boleto",
                "Busque o cliente, escolha a parcela e imprima o documento",
            )
        )

        # ---- passo 1: cliente ----------------------------------------
        busca_card = Card()
        busca_card.body.addWidget(field_label("1. CLIENTE"))
        self.search = SearchBox("Nome, CPF, telefone ou código do cadastro")
        self.search.search.connect(self._search_clients)
        busca_card.body.addWidget(self.search)

        self.clients_table = DataTable(
            ["Código", "Nome", "CPF", "Telefone"], stretch=1, sortable=False
        )
        self.clients_table.setMaximumHeight(170)
        self.clients_table.doubleClicked.connect(lambda *_: self._select_client())
        busca_card.body.addWidget(self.clients_table)

        escolher = button("Selecionar cliente", "users")
        escolher.clicked.connect(self._select_client)
        linha = QHBoxLayout()
        linha.addWidget(escolher)
        linha.addStretch(1)
        busca_card.body.addLayout(linha)
        layout.addWidget(busca_card)

        # ---- passo 2: parcela ----------------------------------------
        layout.addWidget(SectionTitle("2. Parcela a cobrar"))
        self.chosen = QLabel("Nenhum cliente selecionado.")
        self.chosen.setStyleSheet(f"color: {TEXT_MUTED};")
        layout.addWidget(self.chosen)

        self.installments_table = DataTable(
            ["Crediário", "Parcela", "Vencimento", "Valor", "Documento"],
            stretch=1,
            sortable=False,
        )
        self.installments_table.doubleClicked.connect(lambda *_: self._issue())
        layout.addWidget(self.installments_table, 1)

        # ---- passos 3 e 4: gerar e imprimir --------------------------
        acoes = QHBoxLayout()
        self.issue_button = primary_button("Gerar e imprimir", "receipt")
        self.issue_button.setToolTip("Cria a cobrança da parcela e abre o PDF")
        self.issue_button.clicked.connect(self._issue)
        self.issue_button.setEnabled(False)
        self.reprint_button = button("Reimprimir documento", "download")
        self.reprint_button.clicked.connect(self._reprint)
        self.reprint_button.setEnabled(False)
        acoes.addWidget(self.issue_button)
        acoes.addWidget(self.reprint_button)
        acoes.addStretch(1)
        layout.addLayout(acoes)

        self.result = empty_hint(
            "O documento sai em PDF e abre para impressão assim que for gerado."
        )
        layout.addWidget(self.result)

        self._search_clients("")

    # ---- passo 1 -----------------------------------------------------

    def _search_clients(self, term: str = "") -> None:
        rows = client_service.list_clients(
            term, limit=SEARCH_LIMIT, actor=self.ctx.user
        )
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
        linha = self.clients_table.currentRow()
        nome_item = self.clients_table.item(linha, 1)
        self._client_id = int(client_id)
        self._client_name = nome_item.text() if nome_item is not None else ""
        self.refresh()

    # ---- passo 2 -----------------------------------------------------

    def refresh(self) -> None:
        """Recarrega as parcelas do cliente escolhido (só dele)."""
        if self._client_id is None:
            self.installments_table.fill([])
            self.issue_button.setEnabled(False)
            self.reprint_button.setEnabled(False)
            return

        self.chosen.setText(
            f"Cliente: {self._client_name}   •   "
            f"código {client_service.client_code(self._client_id)}"
        )
        self.chosen.setStyleSheet("font-weight: 600;")

        try:
            linhas = charge_service.issuable_for_client(self._client_id, self.ctx.user)
        except PermissionDenied as exc:
            warn(self, "Cobrança", str(exc))
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
                for row in linhas
            ]
        )
        tem_parcela = bool(linhas)
        self.issue_button.setEnabled(tem_parcela)
        self.reprint_button.setEnabled(tem_parcela)
        if not tem_parcela:
            self.result.setText(
                f"{self._client_name} não tem parcelas em aberto para cobrar."
            )
        else:
            self.installments_table.selectRow(0)
            self.result.setText(
                "Escolha a parcela e use Gerar e imprimir. "
                "Se a parcela já tiver documento, use Reimprimir."
            )

    def _selected_installment(self) -> int | None:
        parcela_id = self.installments_table.selected_key()
        if parcela_id is None:
            warn(self, "Parcela", "Escolha a parcela que será cobrada.")
            return None
        return int(parcela_id)

    # ---- passos 3 e 4 ------------------------------------------------

    def _issue(self) -> None:
        parcela_id = self._selected_installment()
        if parcela_id is None:
            return

        existente = charge_service.active_for_installment(parcela_id)
        if existente is not None:
            warn(
                self,
                "Cobrança já emitida",
                f"Esta parcela já tem o documento {existente.numero}. "
                "Use Reimprimir para entregar outra via ao cliente.",
            )
            return

        dialogo = ChargeTypeDialog(self.ctx, self)
        if not dialogo.exec():
            return

        try:
            _, caminho, view = charge_service.create_and_issue(
                parcela_id,
                tipo=dialogo.tipo,
                conta_id=dialogo.conta_id,
                juros=dialogo.juros,
                desconto=dialogo.desconto,
                observacao=dialogo.observacao,
                actor=self.ctx.user,
            )
        except IntegrationNotConfigured as exc:
            warn(self, "Boleto registrado", str(exc))
            return
        except (BusinessError, NotFoundError, ValidationError, PermissionDenied) as exc:
            warn(self, "Cobrança", str(exc))
            return
        except OSError as exc:
            error(self, "Documento", f"Não foi possível gravar o PDF: {exc}")
            return

        self.ctx.notify(f"Cobrança {view.numero} emitida.")
        self.result.setText(f"Documento {view.numero} gerado em {caminho}.")
        open_file(caminho)
        self.refresh()

    def _reprint(self) -> None:
        parcela_id = self._selected_installment()
        if parcela_id is None:
            return
        view = charge_service.active_for_installment(parcela_id)
        if view is None:
            warn(
                self,
                "Sem documento",
                "Esta parcela ainda não tem cobrança. Use Gerar e imprimir.",
            )
            return
        try:
            caminho, _ = charge_service.issue_pdf(view.id, actor=self.ctx.user)
        except PermissionDenied as exc:
            warn(self, "Cobrança", str(exc))
            return
        except OSError as exc:
            error(self, "Documento", f"Não foi possível gravar o PDF: {exc}")
            return
        self.result.setText(f"Documento {view.numero} reimpresso em {caminho}.")
        open_file(caminho)
