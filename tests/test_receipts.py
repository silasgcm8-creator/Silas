"""Comprovante de pagamento: conteúdo, formatos e permissões."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.status import Role
from app.security.permissions import Permission, PermissionDenied, can
from app.services import credit_service, payment_service, receipt_service, user_service
from app.services.errors import BusinessError


@pytest.fixture()
def pagamento(admin, cliente):
    crediario = credit_service.create_credit(
        cliente_id=cliente,
        valor_total=Decimal("600.00"),
        entrada=Decimal("0.00"),
        parcelas=3,
        primeiro_vencimento=date.today() - timedelta(days=18),
        actor=admin,
    )
    parcela = credit_service.get_detail(crediario).installments[0]
    return parcela.id, payment_service.mark_as_paid(parcela.id, admin)


def test_cpf_sai_mascarado_no_comprovante():
    assert receipt_service.mask_cpf("529.982.247-25") == "529.***.**7-25"
    assert receipt_service.mask_cpf("52998224725") == "529.***.**7-25"
    assert receipt_service.mask_cpf("") == "—"


def test_dados_do_comprovante(admin, pagamento):
    _, pagamento_id = pagamento
    dados = receipt_service.build_receipt(pagamento_id)

    assert dados.cliente == "Maria Aparecida Souza"
    assert dados.cpf_mascarado == "529.***.**7-25"
    assert "982" not in dados.cpf_mascarado, "o CPF completo não pode sair impresso"
    assert dados.parcela == "1/3"
    assert dados.valor == Decimal("200.00")
    assert dados.data_pagamento == date.today()
    assert dados.funcionario == "Proprietário SYS"
    assert dados.situacao == "PAGO"
    assert dados.codigo.startswith("PAG-")
    assert dados.registrado_em is not None  # data e hora


def test_gera_pdf_nos_dois_formatos(admin, pagamento, tmp_path):
    _, pagamento_id = pagamento
    for layout in receipt_service.FORMATS:
        destino = tmp_path / f"comprovante_{layout}.pdf"
        caminho, dados = receipt_service.issue(
            pagamento_id, destino, layout=layout, actor=admin
        )
        assert caminho.exists()
        conteudo = caminho.read_bytes()
        assert conteudo.startswith(b"%PDF"), "arquivo precisa ser um PDF de verdade"
        assert conteudo.rstrip().endswith(b"%%EOF"), "PDF precisa estar completo"
        assert len(conteudo) > 800
        assert dados.codigo.startswith("PAG-")


def test_formato_desconhecido_e_recusado(admin, pagamento, tmp_path):
    _, pagamento_id = pagamento
    with pytest.raises(BusinessError):
        receipt_service.issue(pagamento_id, tmp_path / "x.pdf", layout="BOBINA", actor=admin)


def test_comprovante_padrao_vai_para_a_pasta_do_sistema(admin, pagamento):
    from app.config import settings

    _, pagamento_id = pagamento
    caminho, dados = receipt_service.issue(pagamento_id, actor=admin)
    assert caminho.parent == settings.receipt_dir
    assert caminho.name == dados.nome_arquivo(receipt_service.A4)

    # Os dois formatos convivem sem um sobrescrever o outro.
    compacto, _ = receipt_service.issue(
        pagamento_id, layout=receipt_service.COMPACT, actor=admin
    )
    assert compacto != caminho
    assert caminho.exists() and compacto.exists()


def test_funcionario_pode_emitir_comprovante(admin, pagamento, tmp_path):
    """É uma das quatro ações principais do balcão."""
    user_service.create_user("Ana Vendas", "ana", "senha123", Role.STAFF, admin)
    funcionario = user_service.authenticate("ana", "senha123")
    assert can(funcionario.role, Permission.RECEIPT_ISSUE)

    _, pagamento_id = pagamento
    caminho, _ = receipt_service.issue(
        pagamento_id, tmp_path / "func.pdf", actor=funcionario
    )
    assert caminho.exists()


def test_pagamento_estornado_nao_tem_comprovante(admin, pagamento, tmp_path):
    parcela_id, pagamento_id = pagamento
    payment_service.reverse_payment(parcela_id, "Baixa indevida no caixa", admin)

    with pytest.raises(BusinessError):
        receipt_service.issue(pagamento_id, tmp_path / "estornado.pdf", actor=admin)


def test_comprovante_inexistente(admin, tmp_path):
    from app.services.errors import NotFoundError

    with pytest.raises(NotFoundError):
        receipt_service.build_receipt(9999)


def test_emissao_fica_na_auditoria(admin, pagamento, tmp_path):
    from app.database.connection import session_scope
    from app.models.log import LogAction
    from app.services import log_service

    _, pagamento_id = pagamento
    receipt_service.issue(pagamento_id, tmp_path / "auditado.pdf", actor=admin)

    with session_scope() as session:
        assert LogAction.RECEIPT_ISSUED in [e.acao for e in log_service.latest(session)]
