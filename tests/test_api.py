"""API local usada pelo celular: token, permissões e encerramento de sessão."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.status import Role
from app.services import credit_service, payment_service, user_service

# O TestClient do FastAPI é construído sobre o httpx; sem ele o módulo levanta
# RuntimeError, que o importorskip não intercepta. Por isso a checagem é no httpx.
pytest.importorskip("httpx", reason="os testes da API exigem httpx instalado")

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def client():
    from app.api.server import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture()
def crediario(admin, cliente):
    return credit_service.create_credit(
        cliente_id=cliente,
        valor_total=Decimal("600.00"),
        entrada=Decimal("0.00"),
        parcelas=3,
        primeiro_vencimento=date.today() - timedelta(days=18),
        actor=admin,
    )


def login(client, usuario: str = "admin", senha: str = "senha123") -> str:
    resposta = client.post("/auth/login", json={"usuario": usuario, "senha": senha})
    assert resposta.status_code == 200
    return resposta.json()["token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_saude_nao_exige_token(client):
    assert client.get("/saude").status_code == 200


def test_consulta_sem_token_e_recusada(client, admin):
    assert client.get("/clientes").status_code == 401
    assert client.get("/clientes", headers={"Authorization": "Bearer nada"}).status_code == 401


def test_login_e_consulta_do_celular(client, admin, cliente, crediario):
    token = login(client)

    assert client.get("/auth/eu", headers=auth(token)).json()["papel"] == "Administrador"
    assert client.get("/clientes", headers=auth(token)).status_code == 200
    assert client.get("/painel", headers=auth(token)).json()["total_vencido"] == "200.00"
    assert len(client.get("/atrasados", headers=auth(token)).json()) == 1


def test_eu_nunca_devolve_o_token(client, admin):
    token = login(client)
    corpo = client.get("/auth/eu", headers=auth(token)).json()
    assert "token" not in corpo


def test_senha_errada_nao_gera_token(client, admin):
    resposta = client.post("/auth/login", json={"usuario": "admin", "senha": "errada"})
    assert resposta.status_code == 401


def test_logout_invalida_o_token(client, admin, cliente):
    """Celular perdido: encerrar a sessão precisa cortar o acesso na hora."""
    token = login(client)
    assert client.get("/clientes", headers=auth(token)).status_code == 200

    assert client.post("/auth/logout", headers=auth(token)).status_code == 200

    assert client.get("/clientes", headers=auth(token)).status_code == 401
    assert client.post("/auth/logout", headers=auth(token)).status_code == 401


def test_desligar_o_acesso_pelo_celular_encerra_todos_os_aparelhos(client, admin):
    from app.api.server import ApiServer

    token = login(client)
    assert client.get("/clientes", headers=auth(token)).status_code == 200

    # Não sobe servidor de verdade: o desligamento é que precisa limpar os tokens.
    ApiServer().stop()

    assert client.get("/clientes", headers=auth(token)).status_code == 401


def test_funcionario_registra_pagamento_mas_nao_desfaz(client, admin, crediario):
    user_service.create_user("Ana Vendas", "ana", "senha123", Role.STAFF, admin)
    token = login(client, "ana")
    parcela = credit_service.get_detail(crediario).installments[0]

    registro = client.post("/pagamentos", json={"parcela_id": parcela.id}, headers=auth(token))
    assert registro.status_code == 200
    assert credit_service.get_detail(crediario).installments[0].status == "PAGO"

    # Segunda tentativa na mesma parcela: conflito, e o caixa não conta duas vezes.
    repetido = client.post("/pagamentos", json={"parcela_id": parcela.id}, headers=auth(token))
    assert repetido.status_code == 409
    hoje = date.today()
    assert payment_service.total_received(hoje, hoje) == Decimal("200.00")
