"""Pix copia e cola (BR Code), gerado localmente e sem internet.

O padrão do Banco Central é aberto: o "copia e cola" é uma cadeia EMV®QRCPS-MPM
com campos no formato ``ID + tamanho + valor`` e um CRC16 no fim. Aqui é gerado
o **Pix estático da própria empresa**, a partir da chave que o administrador
cadastra — o dinheiro cai na conta dela.

Nada aqui inventa dado bancário de terceiro: sem chave cadastrada, nenhum
código é produzido.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

from app.utils.money import to_decimal

GUI = "br.gov.bcb.pix"
CURRENCY_BRL = "986"
COUNTRY = "BR"
MCC_DEFAULT = "0000"

#: Limites do padrão. Nome e cidade são cortados; a chave nunca é alterada.
MAX_NAME = 25
MAX_CITY = 15
MAX_TXID = 25


def crc16(payload: str) -> str:
    """CRC-16/CCITT-FALSE em hexadecimal maiúsculo de 4 dígitos.

    Polinômio 0x1021 com valor inicial 0xFFFF, como exige o BR Code.
    """
    crc = 0xFFFF
    for byte in payload.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def _field(identifier: str, value: str) -> str:
    return f"{identifier}{len(value):02d}{value}"


def sanitize_text(value: str, limit: int) -> str:
    """Remove acentos e símbolos, que muitos leitores de QR não aceitam."""
    texto = unicodedata.normalize("NFKD", value or "")
    texto = texto.encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^A-Za-z0-9 .-]", "", texto).strip()
    return " ".join(texto.split())[:limit].upper()


def sanitize_txid(value: str) -> str:
    """O identificador aceita apenas letras e números (até 25)."""
    texto = re.sub(r"[^A-Za-z0-9]", "", value or "")
    return texto[:MAX_TXID] or "***"


def build_payload(
    key: str,
    merchant_name: str,
    city: str,
    amount: Decimal | str | None = None,
    txid: str = "***",
) -> str:
    """Monta o Pix copia e cola. Sem chave, não há código: devolve vazio."""
    chave = (key or "").strip()
    if not chave:
        return ""

    nome = sanitize_text(merchant_name, MAX_NAME) or "EMPRESA"
    cidade = sanitize_text(city, MAX_CITY) or "BRASIL"

    conta = _field("00", GUI) + _field("01", chave)

    partes = [
        _field("00", "01"),          # versão do payload
        _field("01", "11"),          # 11 = estático, pode ser usado várias vezes
        _field("26", conta),
        _field("52", MCC_DEFAULT),
        _field("53", CURRENCY_BRL),
    ]

    if amount is not None:
        valor = to_decimal(amount)
        if valor > 0:
            partes.append(_field("54", f"{valor:.2f}"))

    partes.append(_field("58", COUNTRY))
    partes.append(_field("59", nome))
    partes.append(_field("60", cidade))
    partes.append(_field("62", _field("05", sanitize_txid(txid))))

    corpo = "".join(partes) + "6304"
    return corpo + crc16(corpo)


def is_valid_payload(payload: str) -> bool:
    """Confere o CRC de um copia e cola — usado nos testes e na validação."""
    if not payload or len(payload) < 8 or "6304" not in payload:
        return False
    corpo, informado = payload[:-4], payload[-4:]
    if not corpo.endswith("6304"):
        return False
    return crc16(corpo) == informado.upper()
