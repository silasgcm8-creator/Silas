"""Carnê de pagamento: parcelamento, Pix da empresa e áreas de pagamento."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.status import Role
from app.security.permissions import Permission, PermissionDenied, can
from app.services import credit_service, payment_service, slip_service, user_service
from app.services.errors import BusinessError
from app.utils.pix import build_payload, crc16, is_valid_payload

CHAVE = "financeiro@oticasaojose.com.br"


@pytest.fixture()
def crediario(admin, cliente):
    return credit_service.create_credit(
        cliente_id=cliente,
        valor_total=Decimal("1200.00"),
        entrada=Decimal("200.00"),
        parcelas=6,
        primeiro_vencimento=date.today() - timedelta(days=60),
        descricao="2 pares de óculos",
        actor=admin,
    )


# ---- Pix (padrão aberto do Banco Central) --------------------------


def test_crc16_bate_com_o_valor_de_verificacao_do_padrao():
    """CRC-16/CCITT-FALSE de "123456789" é 0x29B1 — checagem oficial do algoritmo."""
    assert crc16("123456789") == "29B1"


def test_payload_do_pix_e_valido_e_conteudo_esperado():
    payload = build_payload(CHAVE, "Ótica São José", "Goiânia", "833.33", "CAR-000001")

    assert is_valid_payload(payload)
    assert payload.startswith("000201")
    assert "br.gov.bcb.pix" in payload
    assert CHAVE in payload
    assert "5406833.33" in payload, "valor precisa entrar no campo 54"
    assert "OTICA SAO JOSE" in payload, "acento não é aceito por muitos leitores"
    assert payload.endswith(crc16(payload[:-4]))


def test_payload_muda_quando_o_valor_muda():
    a = build_payload(CHAVE, "Empresa", "Cidade", "100.00")
    b = build_payload(CHAVE, "Empresa", "Cidade", "200.00")
    assert a != b
    assert is_valid_payload(a) and is_valid_payload(b)


def test_sem_chave_nao_ha_pix():
    """O sistema nunca inventa dado bancário: sem chave, nenhum código sai."""
    assert build_payload("", "Empresa", "Cidade", "100.00") == ""
    assert is_valid_payload("") is False


def test_payload_corrompido_e_detectado():
    payload = build_payload(CHAVE, "Empresa", "Cidade", "50.00")
    assert is_valid_payload(payload[:-1] + "0") is False


# ---- dados do carnê ------------------------------------------------


def test_carne_traz_o_parcelamento_completo(admin, crediario):
    dados = slip_service.build_slip(crediario)

    assert dados.documento == f"CAR-{crediario:06d}"
    assert dados.cliente == "Maria Aparecida Souza"
    assert dados.cpf_mascarado == "529.***.**7-25"
    assert dados.valor_total == Decimal("1200.00")
    assert dados.entrada == Decimal("200.00")
    assert dados.financiado == Decimal("1000.00")
    assert len(dados.installments) == 6
    assert sum(item.valor for item in dados.installments) == Decimal("1000.00")


def test_situacao_de_cada_parcela_no_carne(admin, crediario):
    parcela = credit_service.get_detail(crediario).installments[0]
    payment_service.mark_as_paid(parcela.id, admin)

    dados = slip_service.build_slip(crediario)
    situacoes = [item.situacao for item in dados.installments]

    assert situacoes[0] == "PAGO"
    assert situacoes[1].startswith("ATRASADO"), "2ª parcela venceu há 30 dias"
    assert dados.total_pago == Decimal("166.67")
    assert dados.saldo == Decimal("833.33")


def test_pix_do_carne_usa_o_saldo_devedor(admin, crediario):
    slip_service.save_company_settings("Ótica São José", CHAVE, "Goiânia", admin)
    parcela = credit_service.get_detail(crediario).installments[0]
    payment_service.mark_as_paid(parcela.id, admin)

    dados = slip_service.build_slip(crediario)
    assert dados.tem_pix is True
    assert is_valid_payload(dados.pix_payload)
    assert "5406833.33" in dados.pix_payload


def test_carne_sem_pix_cadastrado_ainda_e_emitido(admin, crediario, tmp_path):
    """A área do Pix fica reservada em branco em vez de bloquear o documento."""
    dados = slip_service.build_slip(crediario)
    assert dados.tem_pix is False

    caminho, _ = slip_service.issue(crediario, tmp_path / "sem_pix.pdf", actor=admin)
    assert caminho.exists()


# ---- PDF -----------------------------------------------------------


def test_pdf_gerado_e_completo(admin, crediario, tmp_path):
    slip_service.save_company_settings("Ótica São José", CHAVE, "Goiânia", admin)
    caminho, dados = slip_service.issue(crediario, tmp_path / "carne.pdf", actor=admin)

    conteudo = caminho.read_bytes()
    assert conteudo.startswith(b"%PDF")
    assert conteudo.rstrip().endswith(b"%%EOF")
    assert len(conteudo) > 3000
    assert dados.tem_pix


def test_pdf_com_pix_e_maior_que_sem_pix(admin, crediario, tmp_path):
    """Confirma que o QR Code realmente foi desenhado no documento."""
    sem, _ = slip_service.issue(crediario, tmp_path / "a.pdf", actor=admin)
    slip_service.save_company_settings("Ótica São José", CHAVE, "Goiânia", admin)
    com, _ = slip_service.issue(crediario, tmp_path / "b.pdf", actor=admin)

    assert com.stat().st_size > sem.stat().st_size


def test_muitas_parcelas_nao_estouram_a_pagina(admin, cliente, tmp_path):
    grande = credit_service.create_credit(
        cliente_id=cliente,
        valor_total=Decimal("6000.00"),
        entrada=Decimal("0.00"),
        parcelas=60,
        primeiro_vencimento=date.today(),
        actor=admin,
    )
    caminho, dados = slip_service.issue(grande, tmp_path / "longo.pdf", actor=admin)
    assert len(dados.installments) == 60
    assert caminho.exists()
    assert caminho.read_bytes().rstrip().endswith(b"%%EOF")


# ---- configuração e permissões -------------------------------------


def test_chave_pix_invalida_e_recusada(admin):
    for ruim in ("abc", "chave com espaco"):
        with pytest.raises(BusinessError):
            slip_service.save_pix_settings(ruim, "Goiânia", admin)


def test_nome_da_empresa_e_obrigatorio(admin):
    with pytest.raises(BusinessError):
        slip_service.save_company_settings("   ", CHAVE, "Goiânia", admin)


def test_funcionario_emite_carne_mas_nao_configura(admin, crediario, tmp_path):
    user_service.create_user("Ana Vendas", "ana", "senha123", Role.STAFF, admin)
    funcionario = user_service.authenticate("ana", "senha123")
    assert can(funcionario.role, Permission.SLIP_ISSUE)

    caminho, _ = slip_service.issue(
        crediario, tmp_path / "func.pdf", actor=funcionario
    )
    assert caminho.exists()

    with pytest.raises(PermissionDenied):
        slip_service.save_company_settings("Outra", CHAVE, "Cidade", funcionario)


def test_emissao_do_carne_fica_na_auditoria(admin, crediario, tmp_path):
    from app.database.connection import session_scope
    from app.models.log import LogAction
    from app.services import log_service

    slip_service.issue(crediario, tmp_path / "auditado.pdf", actor=admin)
    with session_scope() as session:
        assert LogAction.SLIP_ISSUED in [e.acao for e in log_service.latest(session)]


def test_nome_da_empresa_padrao_e_visao(admin, crediario):
    """Instalação nova já sai com o nome da empresa nos documentos."""
    from app.config import COMPANY_DEFAULT

    assert COMPANY_DEFAULT == "VISÃO"
    nome, _, _ = slip_service.company_settings()
    assert nome == "VISÃO"
    assert slip_service.build_slip(crediario).empresa == "VISÃO"


def test_nome_da_empresa_sai_no_comprovante(admin, crediario):
    from app.services import receipt_service

    parcela = credit_service.get_detail(crediario).installments[0]
    pagamento = payment_service.mark_as_paid(parcela.id, admin)
    assert receipt_service.build_receipt(pagamento).empresa == "VISÃO"


def test_nome_da_empresa_pode_ser_alterado(admin, crediario):
    slip_service.save_company_settings("VISÃO ÓTICA CENTRO", CHAVE, "Goiânia", admin)
    assert slip_service.build_slip(crediario).empresa == "VISÃO ÓTICA CENTRO"
