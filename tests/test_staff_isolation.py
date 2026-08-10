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


def test_listagem_de_clientes_nao_traz_dinheiro_para_o_funcionario(
    funcionario, admin, carteira
):
    """Somar linha a linha não pode ser um atalho para o total da carteira."""
    do_funcionario = client_service.list_clients(actor=funcionario)
    assert do_funcionario, "a busca precisa continuar encontrando o cliente"
    for linha in do_funcionario:
        assert linha.saldo is None and linha.vencido is None
        assert linha.nome and linha.cpf and linha.telefone  # o cadastro continua

    do_admin = client_service.list_clients(actor=admin)
    assert all(linha.saldo is not None for linha in do_admin)


def test_listagem_de_crediarios_nao_traz_dinheiro_para_o_funcionario(
    funcionario, admin, carteira
):
    do_funcionario = credit_service.list_credits(actor=funcionario)
    assert do_funcionario
    for linha in do_funcionario:
        assert linha.saldo is None and linha.vencido is None
        # O que ele precisa para atender continua vindo.
        assert linha.parcelas > 0 and linha.valor_total > Decimal("0.00")

    assert all(linha.vencido is not None for linha in credit_service.list_credits(actor=admin))


def test_ficha_do_cliente_sem_totais_para_o_funcionario(funcionario, admin, cliente, carteira):
    ficha = client_service.get_summary(cliente, actor=funcionario)
    assert ficha.nome and ficha.cpf and ficha.telefone
    assert ficha.total_comprado is None
    assert ficha.total_pago is None
    assert ficha.total_aberto is None
    assert ficha.total_vencido is None

    do_admin = client_service.get_summary(cliente, actor=admin)
    assert do_admin.total_comprado > Decimal("0.00")


def test_parcela_vencida_nao_denuncia_atraso_ao_funcionario(funcionario, admin, carteira):
    """Ele escolhe a parcela para receber, mas não vê inadimplência."""
    do_admin = credit_service.get_detail(carteira, actor=admin)
    vencidas = [i for i in do_admin.installments if i.status == "ATRASADO"]
    assert vencidas and vencidas[0].dias_atraso > 0, "o cenário precisa ter atraso real"

    do_funcionario = credit_service.get_detail(carteira, actor=funcionario)
    situacoes = {i.status for i in do_funcionario.installments}
    assert situacoes <= {"PAGO", "EM ABERTO"}
    assert all(i.dias_atraso == 0 for i in do_funcionario.installments)

    # E ele continua conseguindo identificar a parcela a receber.
    abertas = [i for i in do_funcionario.installments if not i.pago]
    assert abertas and abertas[0].valor > Decimal("0.00") and abertas[0].vencimento


def test_cadastros_recentes_so_trazem_dado_operacional(funcionario, admin, cliente, carteira):
    """O que o terminal do balcão lista: identificar e ligar para o cliente."""
    recentes = client_service.recent_clients(actor=funcionario)

    assert [linha.id for linha in recentes] == [cliente]
    linha = recentes[0]
    assert linha.codigo == f"{cliente:06d}"
    assert linha.nome and linha.telefone and linha.cadastrado_em is not None

    # O contrato não tem por onde vazar dinheiro: os campos não existem.
    campos = set(vars(linha))
    assert campos == {"id", "codigo", "nome", "telefone", "cadastrado_em"}


def test_cadastros_recentes_vem_do_mais_novo_para_o_mais_antigo(funcionario, admin):
    primeiro = client_service.create_client(
        "Ana Primeira", "111.444.777-35", "(62) 90000-0001", admin
    )
    segundo = client_service.create_client(
        "Bruno Segundo", "529.982.247-25", "(62) 90000-0002", admin
    )
    recentes = client_service.recent_clients(actor=funcionario)
    assert [linha.id for linha in recentes][:2] == [segundo, primeiro]


def test_busca_do_balcao_encontra_pelo_codigo_interno(funcionario, cliente):
    """O funcionário digita o número impresso no documento."""
    for termo in (str(cliente), f"{cliente:06d}", f"  {cliente}  "):
        achados = client_service.list_clients(termo, actor=funcionario)
        assert [linha.id for linha in achados] == [cliente], f"busca por {termo!r}"


def test_nome_com_numero_nao_vira_busca_por_codigo(funcionario, admin, cliente):
    """"Casa 1" é nome, não código: não pode trazer o cadastro de id 1 junto."""
    alvo = client_service.create_client(
        "Joana Casa 1", "111.444.777-35", "(62) 90000-0001", admin
    )
    achados = client_service.list_clients("Casa 1", actor=funcionario)
    assert [linha.id for linha in achados] == [alvo]


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


# ---- GERAR BOLETO: o fluxo operacional -------------------------------


def test_parcelas_para_cobrar_sao_so_do_cliente_escolhido(funcionario, admin, cliente, carteira):
    from app.services import charge_service

    outro = client_service.create_client(
        "Outro Cliente", "111.444.777-35", "(62) 90000-0001", admin
    )
    credit_service.create_credit(
        cliente_id=outro,
        valor_total=Decimal("500.00"),
        entrada=Decimal("0.00"),
        parcelas=2,
        primeiro_vencimento=HOJE - timedelta(days=30),
        actor=admin,
    )

    linhas = charge_service.issuable_for_client(cliente, funcionario)

    assert linhas, "o cliente tem parcelas em aberto"
    # Nada do outro cliente entra na lista.
    crediarios = {linha.crediario_id for linha in linhas}
    assert crediarios == {carteira}
    # A parcela já paga não aparece: não se cobra o que está quitado.
    assert all(linha.valor > Decimal("0.00") for linha in linhas)
    # E o contrato não tem campo de atraso por onde vazar inadimplência.
    campos = set(vars(linhas[0]))
    assert campos == {
        "parcela_id",
        "crediario_id",
        "parcela",
        "vencimento",
        "valor",
        "documento",
        "documento_id",
    }


def test_funcionario_emite_e_reimprime_a_cobranca(funcionario, cliente, carteira, tmp_path):
    from app.services import charge_service

    parcela = charge_service.issuable_for_client(cliente, funcionario)[0]
    assert parcela.documento is None and not parcela.ja_tem_documento

    documento_id, caminho, view = charge_service.create_and_issue(
        parcela.parcela_id, destination=tmp_path / "cobranca.pdf", actor=funcionario
    )
    assert caminho.stat().st_size > 1000

    # A lista passa a mostrar o documento já emitido para aquela parcela.
    depois = {
        linha.parcela_id: linha
        for linha in charge_service.issuable_for_client(cliente, funcionario)
    }
    assert depois[parcela.parcela_id].documento == view.numero

    # Reimpressão continua liberada para ele.
    novo_caminho, _ = charge_service.issue_pdf(
        documento_id, tmp_path / "segunda-via.pdf", actor=funcionario
    )
    assert novo_caminho.stat().st_size > 1000


def test_lista_de_boletos_nao_marca_atraso_para_o_funcionario(
    funcionario, admin, cliente, carteira, tmp_path
):
    from app.models.charge import STATUS_LATE, STATUS_OPEN
    from app.services import charge_service

    parcela = charge_service.issuable_for_client(cliente, admin)[0]
    charge_service.create_and_issue(
        parcela.parcela_id, destination=tmp_path / "c.pdf", actor=admin
    )

    do_admin = charge_service.list_documents(actor=admin)
    assert any(linha.situacao == STATUS_LATE for linha in do_admin), "o cenário tem atraso"

    do_funcionario = charge_service.list_documents(actor=funcionario)
    assert do_funcionario, "ele continua enxergando o documento para reimprimir"
    assert all(linha.situacao != STATUS_LATE for linha in do_funcionario)
    assert any(linha.situacao == STATUS_OPEN for linha in do_funcionario)

    # E filtrar por ATRASADO não vira uma lista de inadimplentes.
    assert charge_service.list_documents(situacao=STATUS_LATE, actor=funcionario) == []
    assert charge_service.list_documents(situacao=STATUS_LATE, actor=admin)


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


def test_endpoints_do_balcao_nao_devolvem_dinheiro_ao_funcionario(
    api, funcionario, cliente, carteira
):
    """200, mas com os campos financeiros em `null` — não em zero."""
    cabecalho = _token(api, "ana", "senha123")

    for linha in api.get("/clientes", headers=cabecalho).json():
        assert linha["saldo"] is None and linha["vencido"] is None
    for linha in api.get("/crediarios", headers=cabecalho).json():
        assert linha["saldo"] is None and linha["vencido"] is None

    ficha = api.get(f"/clientes/{cliente}", headers=cabecalho).json()
    assert ficha["total_aberto"] is None and ficha["total_vencido"] is None

    crediario = api.get(f"/crediarios/{carteira}", headers=cabecalho).json()
    assert crediario["saldo"] is None and crediario["vencido"] is None
    assert all(item["dias_atraso"] == 0 for item in crediario["itens"])
    assert all(item["situacao"] != "ATRASADO" for item in crediario["itens"])
    # As parcelas continuam lá, com o que ele precisa para receber.
    assert crediario["itens"] and crediario["itens"][0]["valor"]


def test_os_mesmos_endpoints_seguem_completos_para_o_administrador(
    api, admin, cliente, carteira
):
    cabecalho = _token(api, "admin", "senha123")

    assert api.get("/clientes", headers=cabecalho).json()[0]["saldo"] is not None
    crediario = api.get(f"/crediarios/{carteira}", headers=cabecalho).json()
    assert crediario["vencido"] is not None
    assert any(item["dias_atraso"] > 0 for item in crediario["itens"])
