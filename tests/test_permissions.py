"""RBAC: o funcionário não contorna as regras nem pelo código.

Esconder botão não é permissão. Cada teste aqui chama o serviço diretamente,
como faria alguém usando a API do celular ou um script.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.status import Role
from app.security.permissions import (
    ADMIN_PERMISSIONS,
    STAFF_PERMISSIONS,
    Permission,
    PermissionDenied,
)
from app.services import (
    backup_service,
    client_service,
    credit_service,
    payment_service,
    user_service,
)


@pytest.fixture()
def funcionario(admin):
    user_service.create_user("Ana Vendas", "ana", "senha123", Role.STAFF, admin)
    return user_service.authenticate("ana", "senha123")


@pytest.fixture()
def parcela_paga(admin, cliente):
    crediario = credit_service.create_credit(
        cliente_id=cliente,
        valor_total=Decimal("600.00"),
        entrada=Decimal("0.00"),
        parcelas=3,
        primeiro_vencimento=date.today() - timedelta(days=5),
        actor=admin,
    )
    parcela = credit_service.get_detail(crediario).installments[0]
    payment_service.mark_as_paid(parcela.id, admin)
    return parcela.id


def test_funcionario_tem_menos_permissoes_que_o_administrador():
    assert STAFF_PERMISSIONS < ADMIN_PERMISSIONS
    proibidas = {
        Permission.CLIENT_DELETE,
        Permission.PAYMENT_UNDO,
        Permission.BACKUP_RESTORE,
        Permission.USER_MANAGE,
        Permission.LOG_VIEW,
        Permission.SETTINGS,
        Permission.API_CONTROL,
        Permission.DB_CHECK,
        Permission.FINANCE_OVERVIEW,
        Permission.WHATSAPP,
        Permission.CHARGE_VIEW,
    }
    assert proibidas.isdisjoint(STAFF_PERMISSIONS)


def test_funcionario_nao_exclui_cliente(funcionario, cliente):
    with pytest.raises(PermissionDenied):
        client_service.delete_client(cliente, funcionario, "529.982.247-25")
    assert len(client_service.list_clients()) == 1


def test_funcionario_nao_estorna_pagamento(funcionario, admin, parcela_paga):
    with pytest.raises(PermissionDenied):
        payment_service.reverse_payment(parcela_paga, "motivo qualquer", funcionario)

    # O caixa segue intacto.
    hoje = date.today()
    assert payment_service.total_received(hoje, hoje, actor=admin) == Decimal("200.00")


def test_funcionario_nao_restaura_backup(funcionario, admin, tmp_path):
    arquivo = backup_service.create_backup(tmp_path / "b.db", admin)
    with pytest.raises(PermissionDenied):
        backup_service.restore_backup(arquivo, funcionario)


def test_funcionario_nao_verifica_o_banco(funcionario):
    with pytest.raises(PermissionDenied):
        backup_service.check_database(funcionario)


def test_funcionario_nao_cria_usuarios(funcionario):
    with pytest.raises(PermissionDenied):
        user_service.create_user("Outro", "outro", "senha123", Role.STAFF, funcionario)
    with pytest.raises(PermissionDenied):
        user_service.create_user("Chefe", "chefe", "senha123", Role.ADMIN, funcionario)


def test_funcionario_nao_lista_usuarios_nem_desativa(funcionario, admin):
    with pytest.raises(PermissionDenied):
        user_service.list_users(funcionario)
    with pytest.raises(PermissionDenied):
        user_service.set_active(admin.id, False, funcionario)


def test_funcionario_nao_troca_senha_de_outro(funcionario, admin):
    with pytest.raises(PermissionDenied):
        user_service.change_password(admin.id, "novasenha", funcionario)

    # A própria senha ele pode trocar.
    user_service.change_password(funcionario.id, "outrasenha", funcionario)
    assert user_service.authenticate("ana", "outrasenha").id == funcionario.id


def test_funcionario_faz_o_atendimento_do_balcao(funcionario, cliente):
    """O que ele precisa continua liberado — as restrições não travam o trabalho."""
    novo = client_service.create_client(
        "João da Silva", "111.444.777-35", "(62) 98888-7777", funcionario
    )
    crediario = credit_service.create_credit(
        cliente_id=novo,
        valor_total=Decimal("300.00"),
        entrada=Decimal("0.00"),
        parcelas=3,
        primeiro_vencimento=date.today(),
        actor=funcionario,
    )
    parcela = credit_service.get_detail(crediario).installments[0]
    pagamento = payment_service.mark_as_paid(parcela.id, funcionario)
    assert pagamento > 0
