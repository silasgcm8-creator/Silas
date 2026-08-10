"""O valor cobrado é o valor recebido.

Estes testes existem porque o sistema imprimia um documento de R$ 330 e
registrava R$ 300 no caixa. Cada caso aqui reproduz um defeito que já aconteceu
de verdade com dados no banco.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.database.connection import session_scope
from app.models.payment import Payment
from app.services import charge_service, credit_service, payment_service, receipt_service
from app.services.errors import BusinessError, NotFoundError

HOJE = date.today()


@pytest.fixture()
def crediario(admin, cliente):
    """Crediário de R$ 900,00 em três parcelas, a primeira já vencida."""
    return credit_service.create_credit(
        cliente_id=cliente,
        valor_total=Decimal("900.00"),
        entrada=Decimal("0.00"),
        parcelas=3,
        primeiro_vencimento=HOJE - timedelta(days=45),
        actor=admin,
    )


@pytest.fixture()
def parcelas(admin, crediario):
    return credit_service.get_detail(crediario).installments


def _valor_gravado(payment_id: int) -> Decimal:
    with session_scope() as session:
        return session.get(Payment, payment_id).valor


# ---- o dinheiro que entra ------------------------------------------


def test_juros_do_documento_entram_no_caixa(admin, parcelas):
    """O cliente paga o boleto de R$ 330; o caixa não pode registrar R$ 300."""
    documento = charge_service.create(
        parcelas[0].id, juros=Decimal("30.00"), actor=admin
    )
    assert charge_service.build(documento).valor_atualizado == Decimal("330.00")

    pagamento = payment_service.mark_as_paid(
        parcelas[0].id, admin, documento_id=documento
    )

    assert _valor_gravado(pagamento) == Decimal("330.00")
    assert payment_service.total_received(HOJE, HOJE, actor=admin) == Decimal("330.00")


def test_desconto_do_documento_entra_no_caixa(admin, parcelas):
    documento = charge_service.create(
        parcelas[0].id, desconto=Decimal("50.00"), actor=admin
    )
    pagamento = payment_service.mark_as_paid(
        parcelas[0].id, admin, documento_id=documento
    )

    assert _valor_gravado(pagamento) == Decimal("250.00")
    assert payment_service.total_received(HOJE, HOJE, actor=admin) == Decimal("250.00")


def test_sem_documento_o_valor_continua_sendo_o_da_parcela(admin, parcelas):
    pagamento = payment_service.mark_as_paid(parcelas[0].id, admin)
    assert _valor_gravado(pagamento) == Decimal("300.00")


def test_a_divida_e_quitada_pelo_valor_de_face(admin, parcelas, crediario):
    """Recebido e quitado são grandezas diferentes, e as duas ficam certas.

    Com juros, entram R$ 330 no caixa, mas a parcela abate os R$ 300 que ela
    vale — o saldo do crediário não pode encolher a mais por causa da multa.
    """
    documento = charge_service.create(
        parcelas[0].id, juros=Decimal("30.00"), actor=admin
    )
    payment_service.mark_as_paid(parcelas[0].id, admin, documento_id=documento)

    detalhe = credit_service.get_detail(crediario, actor=admin)
    assert detalhe.total_pago == Decimal("300.00")
    assert detalhe.saldo == Decimal("600.00")
    assert payment_service.total_received(HOJE, HOJE, actor=admin) == Decimal("330.00")


def test_estorno_devolve_o_valor_realmente_recebido(admin, parcelas):
    documento = charge_service.create(
        parcelas[0].id, juros=Decimal("30.00"), actor=admin
    )
    payment_service.mark_as_paid(parcelas[0].id, admin, documento_id=documento)
    assert payment_service.total_received(HOJE, HOJE, actor=admin) == Decimal("330.00")

    payment_service.reverse_payment(parcelas[0].id, "Cobranca indevida", admin)
    assert payment_service.total_received(HOJE, HOJE, actor=admin) == Decimal("0.00")


# ---- o documento informado precisa ser o da parcela -----------------


def test_documento_de_outra_parcela_e_recusado(admin, parcelas, crediario):
    """Sem esta conferência, o valor do caixa viria do documento errado."""
    documento = charge_service.create(
        parcelas[1].id, desconto=Decimal("50.00"), actor=admin
    )

    with pytest.raises(BusinessError):
        payment_service.mark_as_paid(parcelas[2].id, admin, documento_id=documento)

    # E a parcela não foi baixada pelo caminho.
    detalhe = credit_service.get_detail(crediario, actor=admin)
    assert not detalhe.installments[2].pago


def test_documento_inexistente_e_recusado(admin, parcelas, crediario):
    with pytest.raises(NotFoundError):
        payment_service.mark_as_paid(parcelas[0].id, admin, documento_id=999999)

    detalhe = credit_service.get_detail(crediario, actor=admin)
    assert not detalhe.installments[0].pago


def test_documento_cancelado_e_recusado(admin, parcelas):
    documento = charge_service.create(parcelas[0].id, actor=admin)
    charge_service.cancel(documento, "Emitido por engano", admin)

    with pytest.raises(BusinessError):
        payment_service.mark_as_paid(parcelas[0].id, admin, documento_id=documento)


# ---- o que o balcão e o cliente enxergam ----------------------------


def test_a_tela_do_caixa_mostra_o_valor_do_documento(admin, parcelas, cliente):
    charge_service.create(parcelas[0].id, juros=Decimal("30.00"), actor=admin)

    linhas = {
        linha.parcela_id: linha
        for linha in payment_service.payable_for_client(cliente, admin)
    }
    com_juros = linhas[parcelas[0].id]
    assert com_juros.valor_parcela == Decimal("300.00")
    assert com_juros.valor_a_receber == Decimal("330.00")
    assert com_juros.tem_ajuste

    sem_documento = linhas[parcelas[1].id]
    assert sem_documento.valor_a_receber == sem_documento.valor_parcela
    assert not sem_documento.tem_ajuste


def test_comprovante_explica_a_diferenca(admin, parcelas):
    documento = charge_service.create(
        parcelas[0].id, juros=Decimal("30.00"), actor=admin
    )
    pagamento = payment_service.mark_as_paid(
        parcelas[0].id, admin, documento_id=documento
    )

    linhas = dict(receipt_service._lines(receipt_service.build_receipt(pagamento)))
    assert linhas["Valor da parcela"] == "R$ 300,00"
    assert linhas["Juros / multa"] == "R$ 30,00"
    assert linhas["Valor recebido"] == "R$ 330,00"


def test_comprovante_sem_ajuste_nao_ganha_linhas_extras(admin, parcelas):
    pagamento = payment_service.mark_as_paid(parcelas[0].id, admin)

    rotulos = [rotulo for rotulo, _ in receipt_service._lines(
        receipt_service.build_receipt(pagamento)
    )]
    assert "Valor da parcela" not in rotulos
    assert "Juros / multa" not in rotulos
    assert "Desconto" not in rotulos


def test_auditoria_guarda_a_composicao_do_valor(admin, parcelas):
    from app.models.log import LogAction
    from app.services import log_service

    documento = charge_service.create(
        parcelas[0].id, juros=Decimal("30.00"), actor=admin
    )
    payment_service.mark_as_paid(parcelas[0].id, admin, documento_id=documento)

    with session_scope() as session:
        detalhes = log_service.latest(
            session, action=LogAction.INSTALLMENT_PAID
        )[0].detalhes
    assert "R$ 330,00" in detalhes
    assert "parcela R$ 300,00" in detalhes
    assert "juros R$ 30,00" in detalhes
