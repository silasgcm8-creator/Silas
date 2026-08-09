"""Registro dos provedores disponíveis.

Trocar de banco no futuro é acrescentar um provedor aqui, sem tocar nas telas
nem nas regras de crediário.
"""

from __future__ import annotations

from app.services.banking.base import BankProvider, BoletoProvider, PixProvider

_PROVIDERS: dict[str, BankProvider] = {
    "boleto": BoletoProvider(),
    "pix": PixProvider(),
}


def provider_for(modalidade: str) -> BankProvider:
    provedor = _PROVIDERS.get(modalidade)
    if provedor is None:
        raise KeyError(f"Provedor desconhecido: {modalidade!r}")
    return provedor


def available_providers() -> dict[str, bool]:
    """Nome do provedor e se ele está pronto para uso."""
    return {nome: provedor.disponivel() for nome, provedor in _PROVIDERS.items()}
