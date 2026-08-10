"""Interface por perfil: o funcionário não enxerga a estrutura administrativa."""

from __future__ import annotations

import os

import pytest

from app.models.status import Role
from app.services import user_service

pytest.importorskip("PySide6", reason="os testes de interface exigem PySide6")

# Sem tela (servidor de CI) o Qt precisa do backend offscreen.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ADMIN_ONLY = ("ATRASADOS", "RELATÓRIOS", "BACKUP", "CONFIGURAÇÕES")


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


def test_recebimentos_do_funcionario_nao_totalizam_o_caixa(qt_app, funcionario, admin):
    from app.ui.context import AppContext
    from app.ui.payments import PaymentsPage

    assert PaymentsPage(AppContext(funcionario)).total_label is None
    assert PaymentsPage(AppContext(admin)).total_label is not None
