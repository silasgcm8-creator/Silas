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


def _dot_is_thousand_separator(cleaned: str) -> bool:
    """Decide se o ponto separa milhar em um texto que não tem vírgula.

    No Brasil `1.500` é mil e quinhentos, não um e meio. Sem essa distinção o
    funcionário que digita `1.500` cadastraria um crediário de R$ 1,50.

    É milhar quando há mais de um ponto (`1.234.567`) ou quando o ponto vem
    seguido de exatamente 3 dígitos (`1.500`). Continua decimal quando a parte
    inteira é apenas `0` (`0.500` = cinquenta centavos) ou quando não são 3
    casas (`1234.56`).
    """
    groups = cleaned.split(".")
    if len(groups) > 2:
        return True
    head, tail = groups
    return len(tail) == 3 and head not in ("", "0")


def parse_brl(text: str) -> Decimal:
    """Aceita '1.234,56', '1.500', '1234.56', 'R$ 1.234,56' e devolve Decimal."""
    cleaned = (text or "").strip()
    for token in ("R$", "r$", " ", "\u00a0"):
        cleaned = cleaned.replace(token, "")
    if not cleaned:
        return ZERO

    negative = cleaned.startswith("-")
    cleaned = cleaned.lstrip("+-")

    if "," in cleaned:
        # Com vírgula, ela é a casa decimal e o ponto é sempre milhar.
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "." in cleaned and _dot_is_thousand_separator(cleaned):
        cleaned = cleaned.replace(".", "")

    try:
        amount = Decimal(cleaned).quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError(f"Valor monetário inválido: {text!r}") from exc
    return -amount if negative else amount


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
