"""Pagamento, estorno, atraso e indicadores."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.services import client_service, credit_service, payment_service, report_service
from app.services.errors import BusinessError


@pytest.fixture()
def crediario(admin, cliente):
    """Crediário com a 1ª parcela vencida e as demais em aberto."""
    primeiro = date.today() - timedelta(days=18)
    return credit_service.create_credit(
        cliente_id=cliente,
        valor_total=Decimal("600.00"),
        entrada=Decimal("0.00"),
        parcelas=3,
        primeiro_vencimento=primeiro,
        actor=admin,
    )


def test_parcela_vencida_e_calculada_automaticamente(crediario):
    itens = credit_service.get_detail(crediario).installments
    assert itens[0].status == "ATRASADO"
    assert itens[0].dias_atraso == 18
    assert itens[1].status == "EM ABERTO"
    assert itens[2].dias_atraso == 0


def test_registro_de_pagamento(admin, cliente, crediario):
    parcela = credit_service.get_detail(crediario).installments[0]
    payment_service.mark_as_paid(parcela.id, admin)

    detalhe = credit_service.get_detail(crediario)
    assert detalhe.installments[0].status == "PAGO"
    assert detalhe.installments[0].pago_em == date.today()
    assert detalhe.total_pago == Decimal("200.00")
    assert detalhe.saldo == Decimal("400.00")

    resumo = client_service.get_summary(cliente)
    assert resumo.total_pago == Decimal("200.00")
    assert resumo.saldo_devedor == Decimal("400.00")
    assert resumo.total_vencido == Decimal("0.00")


def test_pagamento_aparece_nos_recebimentos(admin, crediario):
    parcela = credit_service.get_detail(crediario).installments[0]
    payment_service.mark_as_paid(parcela.id, admin)

    hoje = date.today()
    recebimentos = payment_service.list_payments(hoje, hoje)
    assert len(recebimentos) == 1
    assert recebimentos[0].valor == Decimal("200.00")
    assert recebimentos[0].usuario == "Proprietário SYS"
    assert payment_service.total_received(hoje, hoje) == Decimal("200.00")


def test_pagar_duas_vezes_e_bloqueado(admin, crediario):
    parcela = credit_service.get_detail(crediario).installments[0]
    payment_service.mark_as_paid(parcela.id, admin)
    with pytest.raises(BusinessError):
        payment_service.mark_as_paid(parcela.id, admin)


def test_banco_recusa_dois_recebimentos_da_mesma_parcela(admin, crediario):
    """Rede de segurança contra balcão e celular baixando a mesma parcela."""
    import sqlalchemy as sa

    from app.database.connection import session_scope
    from app.models.payment import Payment

    parcela = credit_service.get_detail(crediario).installments[0]
    payment_service.mark_as_paid(parcela.id, admin)

    with pytest.raises(sa.exc.IntegrityError):
        with session_scope() as session:
            session.add(
                Payment(
                    parcela_id=parcela.id,
                    crediario_id=crediario,
                    cliente_id=1,
                    valor=Decimal("200.00"),
                    data_pagamento=date.today(),
                    usuario_nome="duplicado",
                )
            )

    hoje = date.today()
    assert payment_service.total_received(hoje, hoje) == Decimal("200.00")


def test_baixa_condicional_nao_reabre_parcela_ja_paga(admin, crediario):
    """`settle` só vence a disputa uma vez — a segunda origem recebe False."""
    from app.database.connection import session_scope
    from app.repositories.installment_repository import InstallmentRepository

    parcela = credit_service.get_detail(crediario).installments[0]
    with session_scope() as session:
        repo = InstallmentRepository(session)
        assert repo.settle(parcela.id, date.today()) is True
        assert repo.settle(parcela.id, date.today()) is False


def test_estorno_volta_parcela_para_atrasado(admin, crediario):
    parcela = credit_service.get_detail(crediario).installments[0]
    payment_service.mark_as_paid(parcela.id, admin)
    payment_service.reverse_payment(parcela.id, "Lançado na parcela errada", admin)

    detalhe = credit_service.get_detail(crediario)
    assert detalhe.installments[0].status == "ATRASADO"
    assert detalhe.installments[0].pago_em is None
    assert detalhe.saldo == Decimal("600.00")

    hoje = date.today()
    assert payment_service.list_payments(hoje, hoje) == []
    assert payment_service.total_received(hoje, hoje) == Decimal("0.00")


def test_total_vencido_e_painel(admin, cliente, crediario):
    painel = report_service.dashboard()
    assert painel.total_a_receber == Decimal("600.00")
    assert painel.total_vencido == Decimal("200.00")
    assert painel.parcelas_vencidas == 1
    assert painel.clientes_em_atraso == 1

    atrasados = report_service.late_clients()
    assert len(atrasados) == 1
    assert atrasados[0].vencido == Decimal("200.00")
    assert atrasados[0].parcelas_vencidas == 1
    assert atrasados[0].dias_atraso == 18

    total, mais_antiga, quantidade = report_service.client_overdue_summary(cliente)
    assert total == Decimal("200.00")
    assert quantidade == 1
    assert mais_antiga == date.today() - timedelta(days=18)


def test_pagamento_retira_o_cliente_dos_atrasados(admin, crediario):
    parcela = credit_service.get_detail(crediario).installments[0]
    payment_service.mark_as_paid(parcela.id, admin)
    assert report_service.late_clients() == []
    assert report_service.dashboard().total_vencido == Decimal("0.00")
