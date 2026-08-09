"""Camada de integração bancária.

O sistema funciona **offline** para tudo que é interno. Esta camada existe para
que, no futuro, a cobrança registrada em banco entre por uma API oficial sem
espalhar código de banco pelo resto do programa.

Enquanto não houver integração contratada, o provedor registrado recusa a
emissão com uma mensagem clara. Em nenhuma hipótese o sistema gera nosso
número, linha digitável ou código de barras bancário por conta própria.
"""

from app.services.banking.base import (
    BankProvider,
    BoletoProvider,
    IntegrationNotConfigured,
    PixProvider,
    RegisteredBoleto,
)
from app.services.banking.registry import available_providers, provider_for

__all__ = [
    "BankProvider",
    "BoletoProvider",
    "IntegrationNotConfigured",
    "PixProvider",
    "RegisteredBoleto",
    "available_providers",
    "provider_for",
]
