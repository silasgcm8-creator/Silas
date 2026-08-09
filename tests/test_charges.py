"""Módulo de cobranças: modalidades, documento, histórico e recebimento."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.charge import (
    EVENT_CANCELLED,
    EVENT_CREATED,
    EVENT_PRINTED,
    EVENT_REPRINTED,
    STATUS_CANCELLED,
    STATUS_LATE,
    STATUS_OPEN,
    STATUS_PAID,
    TYPE_BANK,
    TYPE_REGISTERED,
    TYPE_STORE,
)
from app.models.status import PaymentMethod, Role
from app.security.permissions import Permission, PermissionDenied, can
from app.services import (
    bank_account_service,
    charge_service,
    credit_service,
    payment_service,
    receipt_service,
    user_service,
)
from app.services.banking import IntegrationNotConfigured, available_providers
from app.services.errors import BusinessError
from app.utils.validators import ValidationError


@pytest.fixture()
def crediario(admin, cliente):
    """10 parcelas de R$ 250,00; a 1ª já vencida."""
    return credit_service.create_credit(
        cliente_id=cliente,
        valor_total=Decimal("2500.00"),
        entrada=Decimal("0.00"),
        parcelas=10,
        primeiro_vencimento=date.today() - timedelta(days=30),
        descricao="Óculos de grau",
        actor=admin,
    )


@pytest.fixture()
def parcelas(crediario):
    return credit_service.get_detail(crediario).installments


@pytest.fixture()
def conta(admin):
    return bank_account_service.create_account(
        "Banco Principal",
        banco_nome="Banco do Brasil",
        banco_codigo="001",
        agencia="1234",
        agencia_digito="5",
        conta="98765",
        conta_digito="4",
        tipo_conta="Corrente",
        beneficiario_nome="Ótica Visão",
        beneficiario_documento="11.222.333/0001-81",
        pix_chave="financeiro@oticavisao.com.br",
        pix_tipo="E-mail",
        actor=admin,
    )


@pytest.fixture()
def funcionario(admin):
    user_service.create_user("Ana Vendas", "ana", "senha123", Role.STAFF, admin)
    return user_service.authenticate("ana", "senha123")


# ---- criação e numeração --------------------------------------------


def test_documento_da_loja_nao_leva_dado_bancario(admin, parcelas):
    documento = charge_service.create(parcelas[2].id, TYPE_STORE, actor=admin)
    view = charge_service.build(documento)

    assert view.numero == "OV-000001"
    assert view.tipo == TYPE_STORE
    assert view.parcela == "03/10"
    assert view.valor_atualizado == Decimal("250.00")
    assert view.pagamento.linhas() == [], "documento presencial não mostra banco"
    assert view.pagamento.pix_chave == ""


def test_numeracao_sequencial(admin, parcelas):
    primeiro = charge_service.create(parcelas[1].id, actor=admin)
    segundo = charge_service.create(parcelas[2].id, actor=admin)
    assert charge_service.build(primeiro).numero == "OV-000001"
    assert charge_service.build(segundo).numero == "OV-000002"


def test_documento_com_banco_mostra_os_dados_cadastrados(admin, parcelas, conta):
    documento = charge_service.create(
        parcelas[3].id, TYPE_BANK, conta_id=conta, actor=admin
    )
    view = charge_service.build(documento)
    linhas = dict(view.pagamento.linhas())

    assert linhas["Banco"] == "001 — Banco do Brasil"
    assert linhas["Agência"] == "1234-5"
    assert linhas["Conta"] == "98765-4 (Corrente)"
    assert linhas["Beneficiário"] == "Ótica Visão"
    assert linhas["CPF/CNPJ"] == "11.222.333/0001-81"
    assert view.pagamento.pix_chave == "financeiro@oticavisao.com.br"


def test_banco_sem_conta_escolhida_e_recusado(admin, parcelas):
    with pytest.raises(BusinessError, match="conta"):
        charge_service.create(parcelas[1].id, TYPE_BANK, actor=admin)


def test_conta_desativada_nao_pode_ser_usada(admin, parcelas, conta):
    bank_account_service.set_active(conta, False, admin)
    with pytest.raises(BusinessError, match="indisponível"):
        charge_service.create(parcelas[1].id, TYPE_BANK, conta_id=conta, actor=admin)


def test_boleto_registrado_exige_integracao_oficial(admin, parcelas):
    """Sem API do banco, nada é inventado: a emissão é recusada."""
    assert available_providers()["boleto"] is False
    charge_service.save_charge_settings(
        [TYPE_STORE, TYPE_BANK, TYPE_REGISTERED], charge_service.ASK_ALWAYS, admin
    )
    with pytest.raises(IntegrationNotConfigured, match="não está configurada"):
        charge_service.create(parcelas[1].id, TYPE_REGISTERED, actor=admin)


def test_modalidade_nao_liberada_e_recusada(admin, parcelas, conta):
    charge_service.save_charge_settings([TYPE_STORE], TYPE_STORE, admin)
    with pytest.raises(BusinessError, match="não está liberada"):
        charge_service.create(parcelas[1].id, TYPE_BANK, conta_id=conta, actor=admin)


def test_juros_e_desconto_entram_no_valor(admin, parcelas):
    documento = charge_service.create(
        parcelas[1].id, juros="15,50", desconto="5,00", actor=admin
    )
    view = charge_service.build(documento)

    assert view.valor_original == Decimal("250.00")
    assert view.juros == Decimal("15.50")
    assert view.desconto == Decimal("5.00")
    assert view.valor_atualizado == Decimal("260.50")
    assert view.tem_ajuste is True


def test_desconto_nao_pode_zerar_o_valor(admin, parcelas):
    with pytest.raises(ValidationError):
        charge_service.create(parcelas[1].id, desconto="250,00", actor=admin)
    with pytest.raises(ValidationError):
        charge_service.create(parcelas[1].id, juros="-1,00", actor=admin)


def test_uma_cobranca_ativa_por_parcela(admin, parcelas):
    charge_service.create(parcelas[1].id, actor=admin)
    with pytest.raises(BusinessError, match="já possui a cobrança"):
        charge_service.create(parcelas[1].id, actor=admin)


def test_parcela_paga_nao_gera_cobranca(admin, parcelas):
    payment_service.mark_as_paid(parcelas[0].id, admin)
    with pytest.raises(BusinessError, match="já está paga"):
        charge_service.create(parcelas[0].id, actor=admin)


# ---- situação --------------------------------------------------------


def test_situacao_acompanha_a_parcela(admin, parcelas):
    atrasada = charge_service.create(parcelas[0].id, actor=admin)
    aberta = charge_service.create(parcelas[5].id, actor=admin)

    assert charge_service.build(atrasada).situacao == STATUS_LATE
    assert charge_service.build(atrasada).dias_atraso == 30
    assert charge_service.build(aberta).situacao == STATUS_OPEN

    payment_service.mark_as_paid(parcelas[0].id, admin)
    assert charge_service.build(atrasada).situacao == STATUS_PAID


# ---- PDF -------------------------------------------------------------


def test_pdf_dos_dois_modelos(admin, parcelas, conta, tmp_path):
    loja = charge_service.create(parcelas[1].id, TYPE_STORE, actor=admin)
    banco = charge_service.create(parcelas[2].id, TYPE_BANK, conta_id=conta, actor=admin)

    for documento in (loja, banco):
        caminho, _ = charge_service.issue_pdf(
            documento, tmp_path / f"doc_{documento}.pdf", actor=admin
        )
        conteudo = caminho.read_bytes()
        assert conteudo.startswith(b"%PDF")
        assert conteudo.rstrip().endswith(b"%%EOF")
        assert len(conteudo) > 2000


def test_nome_do_arquivo_segue_o_padrao(admin, parcelas):
    documento = charge_service.create(parcelas[2].id, actor=admin)
    nome = charge_service.build(documento).file_name()

    assert nome.startswith("Cobranca_Maria_Aparecida_Souza_Parcela_03_")
    assert nome.endswith(".pdf")


def test_nome_de_arquivo_e_seguro_no_windows():
    assert charge_service.sanitize_filename('Ana: <M/aria>?') == "Ana_Maria"
    assert charge_service.sanitize_filename("José da Silva") == "Jose_da_Silva"
    assert charge_service.sanitize_filename("   ") == "Cliente"
    assert charge_service.sanitize_filename("CON") == "CON_", "nome reservado"
    assert charge_service.sanitize_filename("nome.") == "nome"


def test_qr_interno_nao_leva_dado_pessoal(admin, parcelas):
    documento = charge_service.create(parcelas[2].id, actor=admin)
    view = charge_service.build(documento)

    assert view.qr_content == f"OTICAVISAO:COB:{view.numero}"
    assert "529" not in view.qr_content, "CPF não pode entrar no QR"
    assert "Maria" not in view.qr_content, "nome não pode entrar no QR"


def test_qr_interno_localiza_a_cobranca(admin, parcelas):
    documento = charge_service.create(parcelas[2].id, actor=admin)
    view = charge_service.build(documento)

    assert charge_service.find_by_number(view.qr_content).id == documento
    assert charge_service.find_by_number(view.numero).id == documento
    assert charge_service.find_by_number("OV-999999") is None
    assert charge_service.find_by_number("") is None


# ---- histórico, reimpressão e cancelamento --------------------------


def test_historico_registra_emissao_e_reimpressao(admin, parcelas, tmp_path):
    documento = charge_service.create(parcelas[1].id, actor=admin)
    charge_service.issue_pdf(documento, tmp_path / "a.pdf", actor=admin)
    charge_service.issue_pdf(documento, tmp_path / "b.pdf", actor=admin)

    eventos = [item.evento for item in charge_service.history(documento)]
    assert EVENT_CREATED in eventos
    assert EVENT_PRINTED in eventos
    assert EVENT_REPRINTED in eventos


def test_cancelamento_exige_motivo_e_fica_registrado(admin, parcelas):
    documento = charge_service.create(parcelas[1].id, actor=admin)
    with pytest.raises(ValidationError):
        charge_service.cancel(documento, "abc", admin)

    charge_service.cancel(documento, "Cliente desistiu da compra", admin)
    view = charge_service.build(documento)

    assert view.situacao == STATUS_CANCELLED
    eventos = charge_service.history(documento)
    assert eventos[0].evento == EVENT_CANCELLED
    assert "desistiu" in eventos[0].detalhes


def test_cancelar_libera_nova_cobranca_da_parcela(admin, parcelas):
    primeiro = charge_service.create(parcelas[1].id, actor=admin)
    charge_service.cancel(primeiro, "Valor errado no documento", admin)

    segundo = charge_service.create(parcelas[1].id, juros="10,00", actor=admin)
    assert segundo != primeiro
    assert charge_service.build(segundo).valor_atualizado == Decimal("260.00")


def test_nao_cancela_duas_vezes_nem_parcela_paga(admin, parcelas):
    documento = charge_service.create(parcelas[1].id, actor=admin)
    charge_service.cancel(documento, "Motivo registrado", admin)
    with pytest.raises(BusinessError, match="já está cancelado"):
        charge_service.cancel(documento, "Outro motivo", admin)

    outro = charge_service.create(parcelas[2].id, actor=admin)
    payment_service.mark_as_paid(parcelas[2].id, admin)
    with pytest.raises(BusinessError, match="já foi paga"):
        charge_service.cancel(outro, "Tentativa indevida", admin)


# ---- listagem e filtros ---------------------------------------------


def test_filtros_da_tela_boletos(admin, parcelas, conta):
    atrasado = charge_service.create(parcelas[0].id, actor=admin)
    charge_service.create(parcelas[5].id, TYPE_BANK, conta_id=conta, actor=admin)
    cancelado = charge_service.create(parcelas[6].id, actor=admin)
    charge_service.cancel(cancelado, "Emitido por engano", admin)

    assert len(charge_service.list_documents()) == 3
    assert len(charge_service.list_documents(situacao=STATUS_LATE)) == 1
    assert len(charge_service.list_documents(situacao=STATUS_OPEN)) == 1
    assert len(charge_service.list_documents(situacao=STATUS_CANCELLED)) == 1
    assert len(charge_service.list_documents(tipo=TYPE_BANK)) == 1
    assert len(charge_service.list_documents(conta_id=conta)) == 1

    payment_service.mark_as_paid(parcelas[0].id, admin)
    pagos = charge_service.list_documents(situacao=STATUS_PAID)
    assert [row.id for row in pagos] == [atrasado]


def test_busca_por_nome_cpf_documento_e_parcela(admin, parcelas):
    charge_service.create(parcelas[2].id, actor=admin)

    assert len(charge_service.list_documents(term="Maria")) == 1
    assert len(charge_service.list_documents(term="529.982.247-25")) == 1
    assert len(charge_service.list_documents(term="OV-000001")) == 1
    assert len(charge_service.list_documents(term="3")) == 1  # parcela 3
    assert charge_service.list_documents(term="nao existe") == []


def test_filtro_por_periodo_de_vencimento(admin, parcelas):
    charge_service.create(parcelas[0].id, actor=admin)  # venceu há 30 dias
    hoje = date.today()

    por_emissao = charge_service.list_documents(inicio=hoje, fim=hoje)
    assert len(por_emissao) == 1, "emitido hoje"

    por_vencimento = charge_service.list_documents(
        inicio=hoje, fim=hoje, por_vencimento=True
    )
    assert por_vencimento == [], "o vencimento é antigo"


# ---- recebimento no caixa -------------------------------------------


def test_recebimento_guarda_a_forma_de_pagamento(admin, parcelas):
    documento = charge_service.create(parcelas[1].id, actor=admin)
    view = charge_service.build(documento)

    pagamento = payment_service.mark_as_paid(
        view.parcela_id,
        actor=admin,
        forma_pagamento=PaymentMethod.PIX.value,
        documento_id=documento,
    )

    hoje = date.today()
    recebimentos = payment_service.list_payments(hoje, hoje, actor=admin)
    assert recebimentos[0].forma == "PIX"
    assert recebimentos[0].documento_id == documento

    comprovante = receipt_service.build_receipt(pagamento)
    assert comprovante.forma == "PIX"
    assert comprovante.documento == view.numero
    assert comprovante.situacao == "PAGO"


def test_forma_pode_diferir_da_modalidade_do_documento(admin, parcelas):
    """Documento presencial pago em cartão: o caixa registra o que aconteceu."""
    documento = charge_service.create(parcelas[1].id, TYPE_STORE, actor=admin)
    view = charge_service.build(documento)
    pagamento = payment_service.mark_as_paid(
        view.parcela_id,
        actor=admin,
        forma_pagamento=PaymentMethod.CREDIT.value,
        documento_id=documento,
    )
    assert receipt_service.build_receipt(pagamento).forma == "Cartão de crédito"


def test_forma_desconhecida_cai_em_dinheiro(admin, parcelas):
    pagamento = payment_service.mark_as_paid(
        parcelas[1].id, admin, forma_pagamento="cheque"
    )
    assert receipt_service.build_receipt(pagamento).forma == "Dinheiro"


def test_estorno_do_pagamento_reabre_a_situacao(admin, parcelas):
    documento = charge_service.create(parcelas[5].id, actor=admin)
    view = charge_service.build(documento)
    payment_service.mark_as_paid(
        view.parcela_id, admin, forma_pagamento=PaymentMethod.CASH.value
    )
    assert charge_service.build(documento).situacao == STATUS_PAID

    payment_service.reverse_payment(view.parcela_id, "Lançado por engano", admin)
    assert charge_service.build(documento).situacao == STATUS_OPEN


# ---- permissões ------------------------------------------------------


def test_funcionario_emite_e_recebe_mas_nao_cancela(admin, parcelas, funcionario):
    assert can(funcionario.role, Permission.CHARGE_ISSUE)
    assert can(funcionario.role, Permission.CHARGE_VIEW)
    assert not can(funcionario.role, Permission.CHARGE_CANCEL)
    assert not can(funcionario.role, Permission.BANK_MANAGE)

    documento = charge_service.create(parcelas[2].id, actor=funcionario)
    view = charge_service.build(documento)
    payment_service.mark_as_paid(
        view.parcela_id, funcionario, forma_pagamento=PaymentMethod.CASH.value
    )

    with pytest.raises(PermissionDenied):
        charge_service.cancel(documento, "sem permissão", funcionario)


def test_funcionario_nao_configura_modalidades(admin, funcionario):
    with pytest.raises(PermissionDenied):
        charge_service.save_charge_settings([TYPE_STORE], TYPE_STORE, funcionario)


def test_configuracao_de_modalidades(admin):
    permitidas, padrao = charge_service.save_charge_settings(
        [TYPE_STORE, TYPE_BANK], TYPE_STORE, admin
    )
    assert permitidas == [TYPE_STORE, TYPE_BANK]
    assert padrao == TYPE_STORE
    assert charge_service.allowed_types() == [TYPE_STORE, TYPE_BANK]
    assert charge_service.default_type() == TYPE_STORE

    with pytest.raises(BusinessError):
        charge_service.save_charge_settings([], TYPE_STORE, admin)
    with pytest.raises(BusinessError, match="entre as permitidas"):
        charge_service.save_charge_settings([TYPE_STORE], TYPE_BANK, admin)
