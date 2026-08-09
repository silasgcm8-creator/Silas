"""Cadastro de clientes."""

from __future__ import annotations

import pytest

from app.services import client_service
from app.services.errors import DuplicateClientError, ValidationError


def test_cadastro_e_busca(admin):
    client_id = client_service.create_client(
        "João Carlos Pereira", "529.982.247-25", "62998887766", admin
    )
    encontrado = client_service.find_by_cpf("52998224725")
    assert encontrado is not None
    assert encontrado.id == client_id
    assert encontrado.telefone == "(62) 99888-7766"

    linhas = client_service.list_clients("João")
    assert len(linhas) == 1
    assert linhas[0].saldo == 0


def test_cpf_duplicado_e_bloqueado(admin, cliente):
    with pytest.raises(DuplicateClientError):
        client_service.create_client(
            "Outra Pessoa", "529.982.247-25", "62999990000", admin
        )


def test_cpf_invalido_e_recusado(admin):
    with pytest.raises(ValidationError):
        client_service.create_client("Fulano de Tal", "111.111.111-11", "62999990000", admin)


def test_edicao_mantem_cpf(admin, cliente):
    client_service.update_client(cliente, "Maria A. Souza Lima", "62 98888-1122", admin)
    atualizado = client_service.get_client(cliente)
    assert atualizado.nome == "Maria A. Souza Lima"
    assert atualizado.telefone == "(62) 98888-1122"
    assert atualizado.cpf == "529.982.247-25"


def test_cliente_sem_historico_pode_ser_excluido(admin, cliente):
    assert client_service.can_delete(cliente) is True
    client_service.delete_client(cliente, admin, "529.982.247-25")
    assert client_service.find_by_cpf("52998224725") is None
