"""Estorno auditado: o pagamento sai do caixa mas nunca do histórico."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.database.connection import session_scope
from app.models.log import LogAction
from app.repositories.payment_repository import PaymentRepository
from app.services import credit_service, log_service, payment_service, report_service
from app.services.errors import BusinessError
from app.utils.validators import ValidationError


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


@pytest.fixture()
def paga(admin, crediario):
    """Primeira parcela paga; devolve (parcela_id, pagamento_id)."""
    parcela = credit_service.get_detail(crediario).installments[0]
    return parcela.id, payment_service.mark_as_paid(parcela.id, admin)


def test_pagamento_recebe_codigo_de_operacao(paga):
    _, pagamento_id = paga
    with session_scope() as session:
        pagamento = PaymentRepository(session).get(pagamento_id)
        assert pagamento.codigo.startswith("PAG-")
        assert pagamento.estornado_em is None
        assert pagamento.criado_em is not None  # data e hora do registro


def test_estorno_nao_apaga_o_pagamento(admin, paga):
    parcela_id, pagamento_id = paga
    payment_service.reverse_payment(parcela_id, "Cliente pagou a parcela errada", admin)

    with session_scope() as session:
        repo = PaymentRepository(session)
        pagamento = repo.get(pagamento_id)
        assert pagamento is not None, "o recebimento não pode ser apagado"
        assert pagamento.estornado_em is not None
        # Continua no histórico da parcela, mas não é mais o recebimento válido.
        assert len(repo.history_by_installment(parcela_id)) == 1
        assert repo.get_active_by_installment(parcela_id) is None


def test_estorno_tira_o_valor_do_caixa(admin, paga):
    parcela_id, _ = paga
    hoje = date.today()
    assert payment_service.total_received(hoje, hoje) == Decimal("200.00")

    payment_service.reverse_payment(parcela_id, "Erro de digitação no valor", admin)

    assert payment_service.total_received(hoje, hoje) == Decimal("0.00")
    assert payment_service.list_payments(hoje, hoje) == []
    assert report_service.dashboard().recebido_no_mes == Decimal("0.00")


def test_estorno_guarda_motivo_autor_e_momento(admin, paga):
    parcela_id, _ = paga
    payment_service.reverse_payment(parcela_id, "Duplicidade no caixa", admin)

    hoje = date.today()
    estornos = payment_service.list_reversals(hoje, hoje)
    assert len(estornos) == 1
    estorno = estornos[0]
    assert estorno.motivo == "Duplicidade no caixa"
    assert estorno.usuario == "Proprietário SYS"
    assert estorno.valor == Decimal("200.00")
    assert estorno.pagamento_codigo.startswith("PAG-")
    assert estorno.data.date() == hoje


def test_estorno_entra_na_auditoria(admin, paga):
    parcela_id, _ = paga
    payment_service.reverse_payment(parcela_id, "Motivo registrado", admin)

    with session_scope() as session:
        acoes = [entry.acao for entry in log_service.latest(session)]
    assert LogAction.PAYMENT_REVERSED in acoes


def test_motivo_do_estorno_e_obrigatorio(admin, paga):
    parcela_id, _ = paga
    for invalido in ("", "   ", "abc"):
        with pytest.raises(ValidationError):
            payment_service.reverse_payment(parcela_id, invalido, admin)

    # Nada foi estornado: a parcela continua paga.
    assert payment_service.total_received(date.today(), date.today()) == Decimal("200.00")


def test_parcela_estornada_pode_ser_paga_de_novo(admin, paga, crediario):
    """O índice único é parcial justamente para permitir esta correção."""
    parcela_id, _ = paga
    payment_service.reverse_payment(parcela_id, "Baixa indevida", admin)

    novo_pagamento = payment_service.mark_as_paid(parcela_id, admin)

    hoje = date.today()
    assert payment_service.total_received(hoje, hoje) == Decimal("200.00")
    assert credit_service.get_detail(crediario).installments[0].status == "PAGO"

    with session_scope() as session:
        repo = PaymentRepository(session)
        # Dois registros no histórico, apenas um valendo.
        assert len(repo.history_by_installment(parcela_id)) == 2
        assert repo.get_active_by_installment(parcela_id).id == novo_pagamento


def test_nao_estorna_parcela_em_aberto(admin, crediario):
    aberta = credit_service.get_detail(crediario).installments[1]
    with pytest.raises(BusinessError):
        payment_service.reverse_payment(aberta.id, "Motivo qualquer", admin)


def test_estorno_duas_vezes_e_bloqueado(admin, paga):
    parcela_id, _ = paga
    payment_service.reverse_payment(parcela_id, "Primeiro estorno", admin)
    with pytest.raises(BusinessError):
        payment_service.reverse_payment(parcela_id, "Segundo estorno", admin)
