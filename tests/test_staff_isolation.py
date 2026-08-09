"""O funcionário não alcança a situação financeira da loja nem a inadimplência.

Estes testes não olham para a tela. Cada um chama o serviço ou o endpoint
diretamente — exatamente o que alguém faria digitando a URL no celular, rodando
um script ou importando o módulo no Python. Se a proteção morasse no botão, tudo
aqui passaria mesmo com o vazamento aberto.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.status import Role
from app.security.permissions import Permission, PermissionDenied
from app.services import (
    client_service,
    credit_service,
    payment_service,
    report_service,
    user_service,
)

HOJE = date.today()


@pytest.fixture()
def funcionario(admin):
    user_service.create_user("Ana Vendas", "ana", "senha123", Role.STAFF, admin)
    return user_service.authenticate("ana", "senha123")


@pytest.fixture()
def carteira(admin, cliente):
    """Uma carteira com dinheiro em aberto, vencido e recebido.

    Sem dados reais, um serviço que devolvesse zero passaria por "protegido".
    """
    crediario = credit_service.create_credit(
        cliente_id=cliente,
        valor_total=Decimal("600.00"),
        entrada=Decimal("0.00"),
        parcelas=3,
        primeiro_vencimento=HOJE - timedelta(days=40),
        actor=admin,
    )
    parcelas = credit_service.get_detail(crediario).installments
    payment_service.mark_as_paid(parcelas[0].id, admin)
    return crediario


# ---- serviços: a porta fica antes da consulta ------------------------


def test_funcionario_nao_tem_a_permissao_de_visao_financeira(funcionario, admin):
    assert not funcionario.can(Permission.FINANCE_OVERVIEW)
    assert admin.can(Permission.FINANCE_OVERVIEW)


@pytest.mark.parametrize(
    "chamada",
    [
        pytest.param(lambda u: report_service.dashboard(u), id="painel"),
        pytest.param(lambda u: report_service.report(u, HOJE, HOJE), id="relatorio"),
        pytest.param(lambda u: report_service.late_clients(u), id="inadimplentes"),
        pytest.param(lambda u: report_service.recent_late(u), id="atrasos_recentes"),
        pytest.param(lambda u: report_service.upcoming(u), id="proximos_vencimentos"),
        pytest.param(lambda u: report_service.receivables_rows(u), id="a_receber"),
        pytest.param(
            lambda u: report_service.total_reversed(u, HOJE, HOJE), id="estornado"
        ),
        pytest.param(
            lambda u: report_service.reversals_rows(u, HOJE, HOJE), id="estornos"
        ),
        pytest.param(
            lambda u: payment_service.total_received(HOJE, HOJE, actor=u),
            id="total_recebido",
        ),
        pytest.param(
            lambda u: payment_service.list_reversals(u, HOJE, HOJE), id="lista_estornos"
        ),
        pytest.param(lambda u: client_service.search_totals(u), id="saldo_da_carteira"),
    ],
)
def test_servico_financeiro_recusa_o_funcionario(chamada, funcionario, admin, carteira):
    """Mesmo com dados no banco, o funcionário não recebe número nenhum."""
    with pytest.raises(PermissionDenied):
        chamada(funcionario)

    # E o administrador continua sendo atendido normalmente.
    chamada(admin)


def test_funcionario_nao_monta_mensagem_de_cobranca(funcionario, admin, cliente, carteira):
    """A mensagem do WhatsApp carrega valor vencido e dias de atraso."""
    with pytest.raises(PermissionDenied):
        report_service.client_overdue_summary(funcionario, cliente)

    total, _, quantidade = report_service.client_overdue_summary(admin, cliente)
    assert quantidade > 0 and total > Decimal("0.00")


@pytest.mark.parametrize(
    "exportacao",
    [
        pytest.param(lambda u, p: report_service.export_receivables(u, p), id="a_receber"),
        pytest.param(
            lambda u, p: report_service.export_payments(u, p, HOJE, HOJE), id="pagamentos"
        ),
        pytest.param(
            lambda u, p: report_service.export_reversals(u, p, HOJE, HOJE), id="estornos"
        ),
    ],
)
def test_funcionario_nao_exporta_relatorio_financeiro(
    exportacao, funcionario, admin, carteira, tmp_path
):
    destino = tmp_path / "vazamento.csv"
    with pytest.raises(PermissionDenied):
        exportacao(funcionario, destino)
    assert not destino.exists(), "o arquivo não pode ser escrito antes do bloqueio"

    exportacao(admin, tmp_path / "ok.csv")


# ---- o que o funcionário PODE ver: só a própria operação --------------


def test_funcionario_ve_apenas_os_recebimentos_que_ele_registrou(
    funcionario, admin, cliente, carteira
):
    parcelas = credit_service.get_detail(carteira).installments
    payment_service.mark_as_paid(parcelas[1].id, funcionario)

    do_funcionario = payment_service.list_payments(HOJE, HOJE, actor=funcionario)
    assert [linha.usuario for linha in do_funcionario] == [funcionario.nome]

    # O administrador enxerga os dois recebimentos do dia.
    do_admin = payment_service.list_payments(HOJE, HOJE, actor=admin)
    assert len(do_admin) == 2


def test_o_balcao_continua_funcionando_para_o_funcionario(funcionario):
    """As restrições não podem travar o trabalho do dia a dia."""
    novo = client_service.create_client(
        "João da Silva", "111.444.777-35", "(62) 98888-7777", funcionario
    )
    crediario = credit_service.create_credit(
        cliente_id=novo,
        valor_total=Decimal("300.00"),
        entrada=Decimal("0.00"),
        parcelas=3,
        primeiro_vencimento=HOJE,
        actor=funcionario,
    )
    parcela = credit_service.get_detail(crediario).installments[0]
    assert payment_service.mark_as_paid(parcela.id, funcionario) > 0


# ---- API local: a URL digitada à mão ---------------------------------

pytest.importorskip("httpx", reason="os testes da API exigem httpx instalado")

from fastapi.testclient import TestClient  # noqa: E402

#: Campos que jamais podem sair no corpo de uma resposta para o funcionário.
CAMPOS_PROIBIDOS = (
    "total_a_receber",
    "total_vencido",
    "recebido_no_mes",
    "clientes_em_atraso",
    "parcelas_vencidas",
    "dias_atraso",
)


@pytest.fixture()
def api():
    from app.api.server import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


def _token(api, usuario: str, senha: str) -> dict[str, str]:
    resposta = api.post("/auth/login", json={"usuario": usuario, "senha": senha})
    assert resposta.status_code == 200
    return {"Authorization": f"Bearer {resposta.json()['token']}"}


@pytest.mark.parametrize("rota", ["/painel", "/atrasados"])
def test_endpoint_financeiro_responde_403_ao_funcionario(rota, api, funcionario, carteira):
    resposta = api.get(rota, headers=_token(api, "ana", "senha123"))

    assert resposta.status_code == 403
    corpo = resposta.text
    for campo in CAMPOS_PROIBIDOS:
        assert campo not in corpo, f"{rota} devolveu {campo} junto com o 403"


@pytest.mark.parametrize("rota", ["/painel", "/atrasados"])
def test_o_administrador_continua_com_os_mesmos_endpoints(rota, api, admin, carteira):
    resposta = api.get(rota, headers=_token(api, "admin", "senha123"))
    assert resposta.status_code == 200


def test_parametro_na_url_nao_contorna_o_bloqueio(api, funcionario, carteira):
    """Mexer na query string não muda quem está autenticado."""
    cabecalho = _token(api, "ana", "senha123")
    for consulta in ("?ordem=maior_valor_vencido", "?ordem=admin", "?papel=ADMIN"):
        assert api.get(f"/atrasados{consulta}", headers=cabecalho).status_code == 403


def test_endpoints_do_balcao_seguem_liberados(api, funcionario, cliente, carteira):
    cabecalho = _token(api, "ana", "senha123")
    assert api.get("/clientes", headers=cabecalho).status_code == 200
    assert api.get(f"/clientes/{cliente}", headers=cabecalho).status_code == 200
