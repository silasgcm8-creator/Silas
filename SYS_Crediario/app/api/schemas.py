"""Contratos de entrada e saída da API."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    usuario: str = Field(min_length=3, max_length=32)
    senha: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    token: str
    usuario: str
    nome: str
    papel: str


class ClientOut(BaseModel):
    id: int
    nome: str
    cpf: str
    telefone: str
    saldo: Decimal
    vencido: Decimal
    crediarios: int


class ClientSummaryOut(BaseModel):
    id: int
    nome: str
    cpf: str
    telefone: str
    total_comprado: Decimal
    total_pago: Decimal
    total_aberto: Decimal
    total_vencido: Decimal


class CreditOut(BaseModel):
    id: int
    cliente: str
    cpf: str
    valor_total: Decimal
    entrada: Decimal
    parcelas: int
    pagas: int
    saldo: Decimal
    vencido: Decimal


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
    saldo: Decimal
    vencido: Decimal
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
