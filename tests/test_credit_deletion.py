"""Excluir um crediário lançado por engano.

A regra é uma só e não se move: **sai o que nunca movimentou dinheiro**. Com
pagamento — mesmo já estornado — a exclusão é recusada, porque a história do
caixa não se apaga; ali o caminho é o estorno.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.database.connection import session_scope
from app.models.charge import ChargeDocument
from app.models.credit import Credit
from app.models.installment import Installment
from app.models.log import LogAction
from app.models.status import Role
from app.security.permissions import PermissionDenied
from app.services import (
    charge_service,
    client_service,
    credit_service,
    log_service,
    payment_service,
    user_service,
)
from app.services.errors import BusinessError, NotFoundError, ValidationError

HOJE = date.today()


@pytest.fixture()
def funcionario(admin):
    user_service.create_user("Ana Vendas", "ana", "senha123", Role.STAFF, admin)
    return user_service.authenticate("ana", "senha123")


@pytest.fixture()
def crediario(admin, cliente):
    return credit_service.create_credit(
        cliente_id=cliente,
        valor_total=Decimal("900.00"),
        entrada=Decimal("0.00"),
        parcelas=3,
        primeiro_vencimento=HOJE - timedelta(days=10),
        actor=admin,
    )


def _contar(modelo, **filtros) -> int:
    import sqlalchemy as sa

    with session_scope() as session:
        stmt = sa.select(sa.func.count()).select_from(modelo)
        for coluna, valor in filtros.items():
            stmt = stmt.where(getattr(modelo, coluna) == valor)
        return int(session.scalar(stmt) or 0)


# ---- o que sai -------------------------------------------------------


def test_crediario_sem_pagamento_e_excluido_com_as_parcelas(admin, crediario):
    assert _contar(Installment, crediario_id=crediario) == 3

    resumo = credit_service.delete_credit(crediario, "Lancado no cliente errado", admin)

    assert "R$ 900,00" in resumo
    assert _contar(Credit, id=crediario) == 0
    assert _contar(Installment, crediario_id=crediario) == 0


def test_documentos_de_cobranca_saem_junto(admin, crediario):
    parcelas = credit_service.get_detail(crediario).installments
    charge_service.create(parcelas[0].id, actor=admin)
    assert _contar(ChargeDocument, crediario_id=crediario) == 1

    credit_service.delete_credit(crediario, "Compra cancelada pelo cliente", admin)

    assert _contar(ChargeDocument, crediario_id=crediario) == 0


def test_a_exclusao_fica_na_auditoria(admin, crediario, cliente):
    credit_service.delete_credit(crediario, "Valor digitado errado", admin)

    with session_scope() as session:
        registros = log_service.latest(session, action=LogAction.CREDIT_DELETED)
        assert registros
        entrada = registros[0]
        assert entrada.usuario_nome == admin.nome
        assert entrada.cliente_id == cliente
        assert "Valor digitado errado" in (entrada.detalhes or "")
        assert "R$ 900,00" in (entrada.detalhes or "")


# ---- o que não sai ---------------------------------------------------


def test_crediario_com_pagamento_e_recusado(admin, crediario):
    parcelas = credit_service.get_detail(crediario).installments
    payment_service.mark_as_paid(parcelas[0].id, admin)

    with pytest.raises(BusinessError):
        credit_service.delete_credit(crediario, "Quero apagar mesmo assim", admin)

    assert _contar(Credit, id=crediario) == 1


def test_pagamento_estornado_ainda_protege_o_crediario(admin, crediario):
    """Estorno preserva a história — e história preservada não se apaga."""
    parcelas = credit_service.get_detail(crediario).installments
    payment_service.mark_as_paid(parcelas[0].id, admin)
    payment_service.reverse_payment(parcelas[0].id, "Baixa indevida", admin)

    with pytest.raises(BusinessError):
        credit_service.delete_credit(crediario, "Agora esta zerado", admin)

    assert _contar(Credit, id=crediario) == 1


def test_motivo_e_obrigatorio(admin, crediario):
    for invalido in ("", "   ", "abc"):
        with pytest.raises(ValidationError):
            credit_service.delete_credit(crediario, invalido, admin)
    assert _contar(Credit, id=crediario) == 1


def test_crediario_inexistente(admin):
    with pytest.raises(NotFoundError):
        credit_service.delete_credit(999999, "Nao existe", admin)


def test_funcionario_nao_exclui_crediario(funcionario, crediario):
    with pytest.raises(PermissionDenied):
        credit_service.delete_credit(crediario, "Tentando pelo balcao", funcionario)

    assert _contar(Credit, id=crediario) == 1


# ---- o efeito que o balcão sente -------------------------------------


def test_excluir_o_crediario_destrava_a_exclusao_do_cliente(admin, cliente, crediario):
    """O caso real: cadastrou cliente e crediário errados e ficou preso."""
    from app.services.errors import DuplicateClientError

    with pytest.raises(DuplicateClientError):
        client_service.delete_client(cliente, admin, "529.982.247-25")

    credit_service.delete_credit(crediario, "Cadastro de teste", admin)
    client_service.delete_client(cliente, admin, "529.982.247-25", "Cadastro de teste")

    assert client_service.list_clients() == []


def test_o_crediario_some_das_listas(admin, cliente, crediario):
    assert len(credit_service.list_credits(actor=admin)) == 1
    assert len(credit_service.list_by_client(cliente)) == 1

    credit_service.delete_credit(crediario, "Lancamento duplicado", admin)

    assert credit_service.list_credits(actor=admin) == []
    assert credit_service.list_by_client(cliente) == []
    with pytest.raises(NotFoundError):
        credit_service.get_detail(crediario)
