"""Montagem da mensagem de cobrança e abertura do WhatsApp."""

from __future__ import annotations

import webbrowser
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from urllib.parse import quote

from app.utils.cpf import only_digits
from app.utils.dates import format_br
from app.utils.money import format_brl

DEFAULT_COUNTRY_CODE = "55"

OFFLINE_MESSAGE = (
    "Não foi possível abrir o WhatsApp. Verifique sua conexão com a internet."
)


@dataclass(frozen=True)
class ChargeMessage:
    """Mensagem pronta para conferência do funcionário antes do envio."""

    phone: str
    text: str

    @property
    def url(self) -> str:
        return f"https://wa.me/{self.phone}?text={quote(self.text)}"


def first_name(full_name: str) -> str:
    return (full_name or "").strip().split(" ")[0] or full_name


def normalize_phone(phone: str, country_code: str = DEFAULT_COUNTRY_CODE) -> str:
    digits = only_digits(phone)
    if digits.startswith(country_code) and len(digits) > 11:
        return digits
    return f"{country_code}{digits}"


def build_charge_message(
    client_name: str,
    overdue_total: Decimal,
    oldest_due: date | None,
    overdue_count: int = 1,
) -> str:
    """Texto amigável de cobrança, no modelo aprovado pela empresa."""
    name = first_name(client_name)
    value = format_brl(overdue_total)
    due = format_br(oldest_due) if oldest_due else ""

    if overdue_count > 1:
        detail = (
            f"identificamos parcelas pendentes em seu crediário, totalizando {value}"
            f", sendo a mais antiga com vencimento em {due}"
        )
    else:
        detail = (
            f"identificamos uma parcela do seu crediário no valor de {value}"
            f", com vencimento em {due}"
        )

    return (
        f"Olá, {name}! Tudo bem? 😊\n\n"
        f"Passando apenas para lembrar que {detail}.\n\n"
        "Se você já realizou o pagamento, pode desconsiderar esta mensagem. "
        "Caso ainda não tenha conseguido, fique à vontade para falar conosco "
        "para verificarmos a melhor forma de regularizar.\n\n"
        "Agradecemos pela atenção e pela preferência!"
    )


def build_message(
    client_name: str,
    phone: str,
    overdue_total: Decimal,
    oldest_due: date | None,
    overdue_count: int = 1,
) -> ChargeMessage:
    return ChargeMessage(
        phone=normalize_phone(phone),
        text=build_charge_message(client_name, overdue_total, oldest_due, overdue_count),
    )


def open_whatsapp(message: ChargeMessage) -> bool:
    """Abre o WhatsApp com telefone e texto preenchidos.

    O sistema nunca envia sozinho: apenas prepara a conversa para o funcionário.
    """
    try:
        return bool(webbrowser.open(message.url))
    except Exception:  # pragma: no cover - depende do sistema operacional
        return False
