"""Paginação: base grande não é truncada em silêncio nem carregada inteira."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.services import client_service, credit_service
from app.utils.cpf import format_cpf

pytest.importorskip("httpx", reason="os testes da API exigem httpx instalado")

from fastapi.testclient import TestClient  # noqa: E402

TOTAL = 45


def _cpf(seq: int) -> str:
    """CPF válido determinístico, para criar muitos clientes nos testes."""
    digitos = [int(x) for x in f"{seq:09d}"]
    for _ in range(2):
        peso = len(digitos) + 1
        soma = sum(v * (peso - i) for i, v in enumerate(digitos))
        resto = (soma * 10) % 11
        digitos.append(0 if resto == 10 else resto)
    return format_cpf("".join(map(str, digitos)))


@pytest.fixture()
def base_grande(admin):
    for i in range(TOTAL):
        client_service.create_client(
            f"Cliente Numero {i:04d}", _cpf(200000000 + i), "(62) 99888-7766", admin
        )
    return TOTAL


def test_contagem_independe_da_pagina(admin, base_grande):
    assert client_service.count_clients() == TOTAL
    assert len(client_service.list_clients(limit=10)) == 10
    assert client_service.count_clients() == TOTAL


def test_paginas_nao_repetem_nem_perdem_clientes(admin, base_grande):
    vistos: list[str] = []
    pagina, tamanho = 0, 10
    while True:
        linhas = client_service.list_clients(limit=tamanho, offset=pagina * tamanho)
        if not linhas:
            break
        vistos.extend(row.cpf for row in linhas)
        pagina += 1

    assert len(vistos) == TOTAL
    assert len(set(vistos)) == TOTAL, "nenhum cliente pode aparecer em duas páginas"


def test_ultima_pagina_vem_incompleta(admin, base_grande):
    ultima = client_service.list_clients(limit=10, offset=40)
    assert len(ultima) == 5


def test_contagem_respeita_a_busca(admin, base_grande):
    assert client_service.count_clients("Numero 0007") == 1
    assert client_service.count_clients("nao existe") == 0


def test_totais_somam_toda_a_busca_nao_so_a_pagina(admin, base_grande):
    """O rodapé mostra o total real; somar a página daria número errado."""
    primeiro = client_service.list_clients(limit=1)[0]
    credit_service.create_credit(
        cliente_id=primeiro.id,
        valor_total=Decimal("600.00"),
        entrada=Decimal("0.00"),
        parcelas=3,
        primeiro_vencimento=date.today(),
        actor=admin,
    )

    saldo, _ = client_service.search_totals(admin)
    assert saldo == Decimal("600.00")

    # Em uma página que nem contém o cliente devedor, o total continua correto.
    pagina_sem_devedor = client_service.list_clients(limit=10, offset=30)
    assert all(row.saldo == Decimal("0.00") for row in pagina_sem_devedor)
    assert client_service.search_totals(admin)[0] == Decimal("600.00")


def test_api_pagina_os_clientes(admin, base_grande):
    from app.api.server import create_app

    with TestClient(create_app()) as client:
        token = client.post(
            "/auth/login", json={"usuario": "admin", "senha": "senha123"}
        ).json()["token"]
        cabecalho = {"Authorization": f"Bearer {token}"}

        total = client.get("/clientes/contagem/total", headers=cabecalho)
        assert total.status_code == 200
        assert total.json() == TOTAL

        primeira = client.get(
            "/clientes", params={"pagina": 1, "por_pagina": 10}, headers=cabecalho
        ).json()
        segunda = client.get(
            "/clientes", params={"pagina": 2, "por_pagina": 10}, headers=cabecalho
        ).json()

        assert len(primeira) == len(segunda) == 10
        assert {c["cpf"] for c in primeira}.isdisjoint({c["cpf"] for c in segunda})

        # Página inválida é recusada pelo próprio contrato da API.
        assert client.get(
            "/clientes", params={"pagina": 0}, headers=cabecalho
        ).status_code == 422
