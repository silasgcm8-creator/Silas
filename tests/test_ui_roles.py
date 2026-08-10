"""Interface por perfil: o funcionário não enxerga a estrutura administrativa."""

from __future__ import annotations

import os

import pytest

from app.models.status import Role
from app.services import user_service

pytest.importorskip("PySide6", reason="os testes de interface exigem PySide6")

# Sem tela (servidor de CI) o Qt precisa do backend offscreen.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ADMIN_ONLY = ("ATRASADOS", "RELATÓRIOS", "BACKUP", "CONFIGURAÇÕES", "BOLETOS")


@pytest.fixture(scope="session")
def qt_app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def funcionario(admin):
    user_service.create_user("Ana Vendas", "ana", "senha123", Role.STAFF, admin)
    return user_service.authenticate("ana", "senha123")


def _window(user):
    from app.ui.main_window import MainWindow

    return MainWindow(user)


def test_menu_do_administrador_tem_tudo(qt_app, admin):
    janela = _window(admin)
    for item in ADMIN_ONLY:
        assert item in janela.menu_labels


def test_menu_do_funcionario_esconde_o_administrativo(qt_app, funcionario):
    janela = _window(funcionario)
    for item in ADMIN_ONLY:
        assert item not in janela.menu_labels, f"{item} não é do funcionário"
    # E as telas nem chegam a ser instanciadas para ele.
    for item in ADMIN_ONLY:
        assert item not in janela.pages


def test_funcionario_mantem_o_que_precisa(qt_app, funcionario):
    janela = _window(funcionario)
    for item in ("INÍCIO", "CLIENTES", "RECEBIMENTOS"):
        assert item in janela.menu_labels


def test_home_de_cada_perfil(qt_app, admin, funcionario):
    from app.ui.dashboard import DashboardPage
    from app.ui.staff_home import StaffHomePage

    assert isinstance(_window(admin).home_page, DashboardPage)
    assert isinstance(_window(funcionario).home_page, StaffHomePage)


def test_home_do_funcionario_tem_as_quatro_acoes_grandes(qt_app, funcionario):
    from app.ui.context import AppContext
    from app.ui.staff_home import ACTIONS, BigActionButton, StaffHomePage

    pagina = StaffHomePage(AppContext(funcionario))
    botoes = pagina.findChildren(BigActionButton)
    assert len(botoes) == len(ACTIONS) == 4
    # Todas as quatro ações do balcão estão liberadas para o funcionário.
    assert all(botao.isEnabled() for botao in botoes)
    rotulos = {botao.text().split("\n")[0] for botao in botoes}
    assert rotulos == {
        "NOVO CADASTRO",
        "BUSCAR CLIENTE",
        "REGISTRAR PAGAMENTO",
        "GERAR BOLETO",
    }


def test_cadastros_recentes_aparecem_no_terminal(qt_app, funcionario, cliente):
    from app.ui.context import AppContext
    from app.ui.staff_home import StaffHomePage

    pagina = StaffHomePage(AppContext(funcionario))
    assert pagina.table.rowCount() == 1
    colunas = [
        pagina.table.horizontalHeaderItem(i).text()
        for i in range(pagina.table.columnCount())
    ]
    assert colunas == ["Código", "Nome", "Telefone", "Cadastrado em"]

    linha = [pagina.table.item(0, i).text() for i in range(4)]
    assert linha[0] == f"{cliente:06d}"
    assert "Maria" in linha[1]
    assert "R$" not in " ".join(linha), "a lista não pode carregar dinheiro"


def test_navegacao_do_funcionario_nao_alcanca_tela_administrativa(qt_app, funcionario):
    janela = _window(funcionario)
    assert janela._go("CONFIGURAÇÕES") is None
    assert janela._go("BACKUP") is None


def test_tela_inicial_do_funcionario_nao_tem_valor_nenhum(qt_app, funcionario, cliente):
    """Nem zerado: o componente financeiro não deve existir para ele."""
    from PySide6.QtWidgets import QLabel

    from app.ui.context import AppContext
    from app.ui.staff_home import StaffHomePage

    pagina = StaffHomePage(AppContext(funcionario))
    pagina.refresh()
    textos = " ".join(rotulo.text() for rotulo in pagina.findChildren(QLabel))
    for linha in range(pagina.table.rowCount()):
        for coluna in range(pagina.table.columnCount()):
            textos += " " + pagina.table.item(linha, coluna).text()
    for proibido in ("R$", "Recebido", "vencendo", "vencid", "atras", "saldo"):
        assert proibido not in textos, f"a tela do funcionário mostrou {proibido!r}"


def test_tela_gerar_boleto_existe_para_os_dois_perfis(qt_app, funcionario, admin):
    from app.ui.issue_charge import IssueChargePage

    for usuario in (funcionario, admin):
        janela = _window(usuario)
        assert "GERAR BOLETO" in janela.menu_labels
        assert isinstance(janela.pages["GERAR BOLETO"], IssueChargePage)


def test_gerar_boleto_comeca_sem_parcela_e_sem_indicador(qt_app, funcionario, cliente):
    """A tela é o fluxo do balcão: nada de totais, atrasos ou relatório."""
    from PySide6.QtWidgets import QLabel

    from app.ui.context import AppContext
    from app.ui.issue_charge import IssueChargePage

    pagina = IssueChargePage(AppContext(funcionario))
    # O cliente aparece na busca, mas nenhuma parcela até ele escolher.
    assert pagina.clients_table.rowCount() == 1
    assert pagina.installments_table.rowCount() == 0
    assert not pagina.issue_button.isEnabled()

    textos = " ".join(rotulo.text() for rotulo in pagina.findChildren(QLabel))
    for proibido in ("total", "atras", "vencid", "inadimpl", "R$"):
        assert proibido.lower() not in textos.lower(), f"a tela mostrou {proibido!r}"


def test_gerar_boleto_lista_as_parcelas_do_cliente_escolhido(
    qt_app, funcionario, admin, cliente
):
    from datetime import date, timedelta
    from decimal import Decimal

    from app.services import credit_service
    from app.ui.context import AppContext
    from app.ui.issue_charge import IssueChargePage

    credit_service.create_credit(
        cliente_id=cliente,
        valor_total=Decimal("300.00"),
        entrada=Decimal("0.00"),
        parcelas=3,
        primeiro_vencimento=date.today() - timedelta(days=10),
        actor=admin,
    )

    pagina = IssueChargePage(AppContext(funcionario))
    pagina.clients_table.selectRow(0)
    pagina._select_client()

    assert pagina.installments_table.rowCount() == 3
    assert pagina.issue_button.isEnabled()
    colunas = [
        pagina.installments_table.horizontalHeaderItem(i).text()
        for i in range(pagina.installments_table.columnCount())
    ]
    assert colunas == ["Crediário", "Parcela", "Vencimento", "Valor", "Documento"]
    # Nenhuma coluna de situação: a tela não conta atraso a ninguém.
    assert "Situação" not in colunas


def test_tela_registrar_pagamento_e_o_caixa_do_balcao(qt_app, funcionario, admin, cliente):
    """Cinco passos, sem virar extrato: nem saldo, nem atraso, nem total."""
    from datetime import date, timedelta
    from decimal import Decimal

    from PySide6.QtWidgets import QLabel

    from app.services import credit_service
    from app.ui.context import AppContext
    from app.ui.receive_payment import ReceivePaymentPage

    credit_service.create_credit(
        cliente_id=cliente,
        valor_total=Decimal("300.00"),
        entrada=Decimal("0.00"),
        parcelas=3,
        primeiro_vencimento=date.today() - timedelta(days=10),
        actor=admin,
    )

    pagina = ReceivePaymentPage(AppContext(funcionario))
    assert not pagina.confirm_button.isEnabled()

    pagina.clients_table.selectRow(0)
    pagina._select_client()

    assert pagina.installments_table.rowCount() == 3
    assert pagina.confirm_button.isEnabled()
    # O valor é o da parcela e sai como rótulo: não há campo para digitar
    # outro valor, porque o sistema só baixa parcelas inteiras.
    assert pagina.amount_label.text() == "R$ 100,00"
    assert isinstance(pagina.amount_label, QLabel)

    colunas = [
        pagina.installments_table.horizontalHeaderItem(i).text()
        for i in range(pagina.installments_table.columnCount())
    ]
    assert colunas == ["Crediário", "Parcela", "Vencimento", "Valor", "Documento"]

    textos = " ".join(rotulo.text() for rotulo in pagina.findChildren(QLabel))
    for proibido in ("saldo", "atras", "vencid", "total recebido", "inadimpl"):
        assert proibido.lower() not in textos.lower(), f"a tela mostrou {proibido!r}"


def test_registrar_pagamento_baixa_a_parcela_e_libera_o_comprovante(
    qt_app, funcionario, admin, cliente, monkeypatch
):
    from datetime import date
    from decimal import Decimal

    from app.services import credit_service
    from app.ui.context import AppContext
    from app.ui.receive_payment import ReceivePaymentPage

    credit_service.create_credit(
        cliente_id=cliente,
        valor_total=Decimal("200.00"),
        entrada=Decimal("0.00"),
        parcelas=2,
        primeiro_vencimento=date.today(),
        actor=admin,
    )

    pagina = ReceivePaymentPage(AppContext(funcionario))
    pagina.clients_table.selectRow(0)
    pagina._select_client()
    assert pagina.installments_table.rowCount() == 2

    # Confirma sem abrir a caixa de diálogo do Qt (monkeypatch se desfaz sozinho).
    monkeypatch.setattr(
        "app.ui.receive_payment.confirm", lambda *_a, **_k: True
    )
    pagina.note_edit.setText("recebido no balcão")
    pagina._register()

    assert pagina._last_payment is not None
    assert pagina.receipt_button.isEnabled()
    # A parcela paga sai da lista imediatamente.
    assert pagina.installments_table.rowCount() == 1
    # E a confirmação da operação fica na tela, não é sobrescrita pela recarga.
    assert "baixada" in pagina.result.text()


def test_atalho_atrasados_da_tela_de_boletos_e_so_do_administrador(
    qt_app, funcionario, admin
):
    from app.models.charge import STATUS_LATE
    from app.ui.charges import ChargesPage
    from app.ui.context import AppContext

    assert STATUS_LATE not in ChargesPage(AppContext(funcionario)).quick_buttons
    assert STATUS_LATE in ChargesPage(AppContext(admin)).quick_buttons


def test_recebimentos_do_funcionario_nao_totalizam_o_caixa(qt_app, funcionario, admin):
    from app.ui.context import AppContext
    from app.ui.payments import PaymentsPage

    assert PaymentsPage(AppContext(funcionario)).total_label is None
    assert PaymentsPage(AppContext(admin)).total_label is not None
