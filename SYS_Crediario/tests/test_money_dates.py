"""Cálculo de parcelas, diferença de centavos e geração de datas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.utils.dates import add_months, days_late
from app.utils.money import format_brl, parse_brl, split_installments


def test_divisao_exata():
    parcelas = split_installments(Decimal("1000.00"), 5)
    assert parcelas == [Decimal("200.00")] * 5
    assert sum(parcelas) == Decimal("1000.00")


def test_diferenca_de_centavos_vai_para_ultima_parcela():
    parcelas = split_installments(Decimal("100.00"), 3)
    assert parcelas[:2] == [Decimal("33.33"), Decimal("33.33")]
    assert parcelas[-1] == Decimal("33.34")
    assert sum(parcelas) == Decimal("100.00")


def test_soma_sempre_igual_ao_financiado():
    for total in ("1000.00", "999.99", "1234.57", "0.05", "7.77"):
        for count in (1, 2, 3, 6, 7, 12, 60):
            parcelas = split_installments(Decimal(total), count)
            assert len(parcelas) == count
            assert sum(parcelas) == Decimal(total)


def test_parcelas_invalidas():
    with pytest.raises(ValueError):
        split_installments(Decimal("100.00"), 0)


def test_geracao_de_datas_mes_a_mes():
    primeiro = date(2026, 1, 31)
    vencimentos = [add_months(primeiro, i) for i in range(4)]
    assert vencimentos == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
        date(2026, 4, 30),
    ]


def test_ano_bissexto_e_virada_de_ano():
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert add_months(date(2026, 11, 15), 3) == date(2027, 2, 15)


def test_dias_de_atraso():
    assert days_late(date(2026, 8, 1), date(2026, 8, 19)) == 18
    assert days_late(date(2026, 8, 20), date(2026, 8, 19)) == 0


def test_formatacao_brasileira():
    assert format_brl(Decimal("1234.5")) == "R$ 1.234,50"
    assert parse_brl("R$ 1.234,50") == Decimal("1234.50")
    assert parse_brl("1234.50") == Decimal("1234.50")
