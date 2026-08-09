"""Criação de crediários e geração das parcelas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.services import client_service, credit_service
from app.services.errors import ValidationError


def criar_crediario(admin, cliente, total="1200.00", entrada="200.00", parcelas=5):
    return credit_service.create_credit(
        cliente_id=cliente,
        valor_total=Decimal(total),
        entrada=Decimal(entrada),
        parcelas=parcelas,
        primeiro_vencimento=date(2026, 1, 10),
        descricao="Compra de teste",
        actor=admin,
    )


def test_exemplo_do_manual(admin, cliente):
    credit_id = criar_crediario(admin, cliente)
    detalhe = credit_service.get_detail(credit_id)

    assert detalhe.valor_total == Decimal("1200.00")
    assert detalhe.entrada == Decimal("200.00")
    assert detalhe.financiado == Decimal("1000.00")
    assert len(detalhe.installments) == 5
    assert all(item.valor == Decimal("200.00") for item in detalhe.installments)
    assert sum(item.valor for item in detalhe.installments) == Decimal("1000.00")


def test_datas_geradas_mes_a_mes(admin, cliente):
    credit_id = criar_crediario(admin, cliente)
    vencimentos = [i.vencimento for i in credit_service.get_detail(credit_id).installments]
    assert vencimentos == [
        date(2026, 1, 10),
        date(2026, 2, 10),
        date(2026, 3, 10),
        date(2026, 4, 10),
        date(2026, 5, 10),
    ]


def test_ajuste_de_centavos_na_ultima_parcela(admin, cliente):
    credit_id = criar_crediario(admin, cliente, total="100.00", entrada="0.00", parcelas=3)
    itens = credit_service.get_detail(credit_id).installments
    assert [i.valor for i in itens] == [
        Decimal("33.33"),
        Decimal("33.33"),
        Decimal("33.34"),
    ]
    assert sum(i.valor for i in itens) == Decimal("100.00")


def test_numeracao_das_parcelas(admin, cliente):
    credit_id = criar_crediario(admin, cliente, parcelas=6)
    itens = credit_service.get_detail(credit_id).installments
    assert [i.rotulo for i in itens] == ["1/6", "2/6", "3/6", "4/6", "5/6", "6/6"]


def test_entrada_maior_que_a_compra_e_recusada(admin, cliente):
    with pytest.raises(ValidationError):
        criar_crediario(admin, cliente, total="500.00", entrada="500.00")


def test_saldo_do_cliente_apos_criacao(admin, cliente):
    criar_crediario(admin, cliente)
    resumo = client_service.get_summary(cliente)
    assert resumo.total_comprado == Decimal("1200.00")
    assert resumo.total_aberto == Decimal("1000.00")
    assert resumo.saldo_devedor == Decimal("1000.00")
