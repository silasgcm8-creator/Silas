"""Aritmética monetária exata em Decimal e formatação em Real."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")
ZERO = Decimal("0.00")

Money = Decimal


def to_decimal(value: object) -> Decimal:
    """Converte int/float/str/Decimal para Decimal com 2 casas."""
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int):
        result = Decimal(value)
    elif isinstance(value, float):
        result = Decimal(str(value))
    elif isinstance(value, str):
        result = parse_brl(value)
    elif value is None:
        result = ZERO
    else:
        raise TypeError(f"Valor monetário inválido: {value!r}")
    return result.quantize(CENT, rounding=ROUND_HALF_UP)


def to_cents(value: object) -> int:
    return int(to_decimal(value) * 100)


def from_cents(cents: int | None) -> Decimal:
    return (Decimal(int(cents or 0)) / 100).quantize(CENT)


def parse_brl(text: str) -> Decimal:
    """Aceita '1.234,56', '1234.56', 'R$ 1.234,56' e devolve Decimal."""
    cleaned = (text or "").strip()
    for token in ("R$", "r$", " ", "\u00a0"):
        cleaned = cleaned.replace(token, "")
    if not cleaned:
        return ZERO
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned).quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:  # pragma: no cover - defensivo
        raise ValueError(f"Valor monetário inválido: {text!r}") from exc


def format_brl(value: object, symbol: bool = True) -> str:
    amount = to_decimal(value)
    negative = amount < 0
    text = f"{abs(amount):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    prefix = "R$ " if symbol else ""
    return f"-{prefix}{text}" if negative else f"{prefix}{text}"


def split_installments(financed: Decimal, count: int) -> list[Decimal]:
    """Divide o valor financiado em `count` parcelas.

    A diferença de centavos causada pela divisão é somada à última parcela,
    garantindo que a soma seja exatamente igual ao valor financiado.
    """
    if count < 1:
        raise ValueError("Quantidade de parcelas deve ser maior que zero.")
    total = to_decimal(financed)
    base = (total / count).quantize(CENT, rounding=ROUND_HALF_UP)
    values = [base] * (count - 1)
    values.append((total - base * (count - 1)).quantize(CENT))
    return values
