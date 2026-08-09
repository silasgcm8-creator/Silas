"""Exclusão lógica de cliente: sai das listas, nunca do banco."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.database.connection import session_scope
from app.models.client import Client
from app.models.log import LogAction
from app.models.status import Role
from app.security.permissions import PermissionDenied
from app.services import client_service, credit_service, log_service, user_service
from app.services.errors import BusinessError, DuplicateClientError, NotFoundError

CPF = "529.982.247-25"


def test_exclusao_nao_apaga_do_banco(admin, cliente):
    client_service.delete_client(cliente, admin, CPF, "Cadastro duplicado")

    assert client_service.list_clients() == []
    assert client_service.count_clients() == 0

    with session_scope() as session:
        registro = session.get(Client, cliente)
        assert registro is not None, "o cadastro não pode ser apagado"
        assert registro.excluido is True
        assert registro.excluido_por == "Proprietário SYS"
        assert registro.motivo_exclusao == "Cadastro duplicado"
        assert registro.excluido_em is not None


def test_exclusao_exige_cpf_correto(admin, cliente):
    with pytest.raises(NotFoundError):
        client_service.delete_client(cliente, admin, "111.444.777-35", "motivo")
    assert client_service.count_clients() == 1


def test_reativacao_devolve_o_cliente(admin, cliente):
    client_service.delete_client(cliente, admin, CPF, "engano")
    client_service.restore_client(cliente, admin)

    assert client_service.count_clients() == 1
    with session_scope() as session:
        registro = session.get(Client, cliente)
        assert registro.excluido is False
        assert registro.motivo_exclusao is None


def test_reativar_cliente_ativo_e_recusado(admin, cliente):
    with pytest.raises(BusinessError):
        client_service.restore_client(cliente, admin)


def test_cliente_com_historico_nunca_e_excluido(admin, cliente):
    credit_service.create_credit(
        cliente_id=cliente,
        valor_total=Decimal("300.00"),
        entrada=Decimal("0.00"),
        parcelas=3,
        primeiro_vencimento=date.today(),
        actor=admin,
    )
    assert client_service.can_delete(cliente) is False
    with pytest.raises(DuplicateClientError):
        client_service.delete_client(cliente, admin, CPF, "tentativa")
    assert client_service.count_clients() == 1


def test_cpf_de_excluido_orienta_a_reativar(admin, cliente):
    """Sem isso o recadastro estouraria a restrição do banco com erro técnico."""
    client_service.delete_client(cliente, admin, CPF, "duplicado")

    with pytest.raises(DuplicateClientError, match="excluído"):
        client_service.create_client("Outra Pessoa", CPF, "(62) 90000-0000", admin)


def test_excluido_nao_aparece_na_busca_por_cpf(admin, cliente):
    client_service.delete_client(cliente, admin, CPF, "saiu")
    assert client_service.find_by_cpf(CPF) is None


def test_listagem_de_excluidos_mostra_a_trilha(admin, cliente):
    client_service.delete_client(cliente, admin, CPF, "Cliente pediu remoção")
    excluidos = client_service.list_deleted(admin)

    assert len(excluidos) == 1
    assert excluidos[0].nome == "Maria Aparecida Souza"
    assert excluidos[0].excluido_por == "Proprietário SYS"
    assert excluidos[0].motivo == "Cliente pediu remoção"


def test_exclusao_e_reativacao_entram_na_auditoria(admin, cliente):
    client_service.delete_client(cliente, admin, CPF, "motivo auditado")
    client_service.restore_client(cliente, admin)

    with session_scope() as session:
        acoes = [entry.acao for entry in log_service.latest(session)]
    assert LogAction.CLIENT_DELETED in acoes
    assert LogAction.CLIENT_RESTORED in acoes


def test_funcionario_nao_exclui_nem_reativa(admin, cliente):
    user_service.create_user("Ana Vendas", "ana", "senha123", Role.STAFF, admin)
    funcionario = user_service.authenticate("ana", "senha123")

    with pytest.raises(PermissionDenied):
        client_service.delete_client(cliente, funcionario, CPF, "sem permissão")
    with pytest.raises(PermissionDenied):
        client_service.list_deleted(funcionario)
    with pytest.raises(PermissionDenied):
        client_service.restore_client(cliente, funcionario)
