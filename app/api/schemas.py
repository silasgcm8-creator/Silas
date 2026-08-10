"""Contratos de entrada e saída da API."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    usuario: str = Field(min_length=3, max_length=32)
    senha: str = Field(min_length=1, max_length=128)


class IdentityOut(BaseModel):
    """Quem está autenticado, sem devolver token."""

    usuario: str
    nome: str
    papel: str


class TokenOut(IdentityOut):
    token: str


class ClientOut(BaseModel):
    """Saldo e vencido saem `null` para quem não tem a visão financeira."""

    id: int
    nome: str
    cpf: str
    telefone: str
    saldo: Decimal | None = None
    vencido: Decimal | None = None
    crediarios: int


class ClientSummaryOut(BaseModel):
    id: int
    nome: str
    cpf: str
    telefone: str
    total_comprado: Decimal | None = None
    total_pago: Decimal | None = None
    total_aberto: Decimal | None = None
    total_vencido: Decimal | None = None


class CreditOut(BaseModel):
    id: int
    cliente: str
    cpf: str
    valor_total: Decimal
    entrada: Decimal
    parcelas: int
    pagas: int
    saldo: Decimal | None = None
    vencido: Decimal | None = None


class InstallmentOut(BaseModel):
    id: int
    parcela: str
    vencimento: date
    valor: Decimal
    situacao: str
    dias_atraso: int
    pago_em: date | None = None


class CreditDetailOut(BaseModel):
    id: int
    cliente: str
    cpf: str
    telefone: str
    valor_total: Decimal
    entrada: Decimal
    parcelas: int
    saldo: Decimal | None = None
    vencido: Decimal | None = None
    itens: list[InstallmentOut]


class LateOut(BaseModel):
    cliente_id: int
    cliente: str
    cpf: str
    telefone: str
    vencido: Decimal
    saldo: Decimal
    parcelas_vencidas: int
    vencimento_antigo: date | None
    dias_atraso: int


class DashboardOut(BaseModel):
    total_a_receber: Decimal
    total_vencido: Decimal
    recebido_no_mes: Decimal
    clientes_em_atraso: int
    parcelas_vencendo_hoje: int
    parcelas_vencidas: int


class PaymentIn(BaseModel):
    parcela_id: int
    data_pagamento: date | None = None


class MessageOut(BaseModel):
    mensagem: str
