"""Indicadores do painel, tela de atrasados e relatórios por período.

Todo número deste módulo descreve a loja inteira — quanto há a receber, quanto
entrou, quem está em atraso. Nada aqui é operação de balcão. Por isso cada
função exige o usuário que está perguntando e confere
``Permission.FINANCE_OVERVIEW`` **antes** de consultar o banco: a proteção vive
aqui, não na tela nem na rota, e vale igual para a interface, para a API do
celular e para qualquer script que importe o módulo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

import sqlalchemy as sa

from app.database.connection import session_scope
from app.database.types import sum_cents
from app.models.client import Client
from app.models.credit import Credit
from app.models.installment import Installment
from app.models.payment import Payment
from app.repositories.installment_repository import InstallmentRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.reversal_repository import ReversalRepository
from app.security.authentication import SessionUser
from app.security.permissions import Permission, require
from app.utils.dates import days_late, format_br, format_datetime_br, month_bounds
from app.utils.export import export
from app.utils.money import ZERO, format_brl, from_cents


def _require_overview(actor: SessionUser) -> None:
    """Porta única deste módulo. Roda antes de qualquer consulta."""
    require(actor.role, Permission.FINANCE_OVERVIEW)


@dataclass(frozen=True)
class DashboardData:
    total_a_receber: Decimal
    total_vencido: Decimal
    recebido_hoje: Decimal
    recebido_no_mes: Decimal
    clientes_em_atraso: int
    parcelas_vencendo_hoje: int
    valor_vencendo_hoje: Decimal
    parcelas_vencidas: int
    parcelas_em_aberto: int
    total_clientes: int
    pagamentos_no_mes: int


@dataclass(frozen=True)
class UpcomingRow:
    cliente: str
    cpf: str
    vencimento: date
    valor: Decimal
    parcela: str
    crediario_id: int


@dataclass(frozen=True)
class LateRow:
    cliente_id: int
    cliente: str
    cpf: str
    telefone: str
    vencido: Decimal
    saldo: Decimal
    parcelas_vencidas: int
    vencimento_antigo: date | None

    @property
    def dias_atraso(self) -> int:
        return days_late(self.vencimento_antigo) if self.vencimento_antigo else 0


@dataclass(frozen=True)
class ReportData:
    inicio: date
    fim: date
    total_vendido: Decimal
    total_recebido: Decimal
    total_a_receber: Decimal
    total_vencido: Decimal
    clientes_ativos: int
    clientes_em_atraso: int
    parcelas_vencidas: int
    vencimentos_futuros: Decimal

    def as_rows(self) -> list[tuple[str, str]]:
        return [
            ("Período", f"{format_br(self.inicio)} a {format_br(self.fim)}"),
            ("Total vendido no período", format_brl(self.total_vendido)),
            ("Total recebido no período", format_brl(self.total_recebido)),
            ("Total a receber (geral)", format_brl(self.total_a_receber)),
            ("Total vencido (geral)", format_brl(self.total_vencido)),
            ("Clientes ativos", str(self.clientes_ativos)),
            ("Clientes em atraso", str(self.clientes_em_atraso)),
            ("Parcelas vencidas", str(self.parcelas_vencidas)),
            ("Vencimentos futuros", format_brl(self.vencimentos_futuros)),
        ]


def dashboard(actor: SessionUser, reference: date | None = None) -> DashboardData:
    _require_overview(actor)
    reference = reference or date.today()
    month_start, month_end = month_bounds(reference)

    with session_scope() as session:
        open_total = session.scalar(
            sa.select(sum_cents(Installment.valor)).where(Installment.pago.is_(False))
        )
        overdue_total = session.scalar(
            sa.select(sum_cents(Installment.valor)).where(
                Installment.pago.is_(False), Installment.vencimento < reference
            )
        )
        overdue_count = session.scalar(
            sa.select(sa.func.count(Installment.id)).where(
                Installment.pago.is_(False), Installment.vencimento < reference
            )
        )
        late_clients = session.scalar(
            sa.select(sa.func.count(sa.distinct(Credit.cliente_id)))
            .select_from(Credit)
            .join(Installment, Installment.crediario_id == Credit.id)
            .where(Installment.pago.is_(False), Installment.vencimento < reference)
        )
        today_count, today_cents = InstallmentRepository(session).due_today_total(reference)
        payments = PaymentRepository(session)
        received = payments.total_period(month_start, month_end)
        received_today = payments.total_period(reference, reference)
        open_count = session.scalar(
            sa.select(sa.func.count(Installment.id)).where(Installment.pago.is_(False))
        )
        clients_count = session.scalar(sa.select(sa.func.count(Client.id)))
        month_payments = session.scalar(
            sa.select(sa.func.count(Payment.id)).where(
                Payment.data_pagamento.between(month_start, month_end),
                Payment.estornado_em.is_(None),
            )
        )

    return DashboardData(
        total_a_receber=from_cents(open_total or 0),
        total_vencido=from_cents(overdue_total or 0),
        recebido_hoje=from_cents(received_today),
        recebido_no_mes=from_cents(received),
        clientes_em_atraso=int(late_clients or 0),
        parcelas_vencendo_hoje=today_count,
        valor_vencendo_hoje=from_cents(today_cents),
        parcelas_vencidas=int(overdue_count or 0),
        parcelas_em_aberto=int(open_count or 0),
        total_clientes=int(clients_count or 0),
        pagamentos_no_mes=int(month_payments or 0),
    )


def upcoming(
    actor: SessionUser, reference: date | None = None, limit: int = 15
) -> list[UpcomingRow]:
    _require_overview(actor)
    with session_scope() as session:
        rows = InstallmentRepository(session).upcoming(reference, limit)
        return [
            UpcomingRow(
                cliente=row.nome,
                cpf=row.cpf,
                vencimento=row.vencimento,
                valor=row.valor,
                parcela=f"{row.numero}/{row.parcelas}",
                crediario_id=row.crediario_id,
            )
            for row in rows
        ]


def recent_late(
    actor: SessionUser, reference: date | None = None, limit: int = 10
) -> list[UpcomingRow]:
    _require_overview(actor)
    with session_scope() as session:
        rows = InstallmentRepository(session).recent_late(reference, limit)
        return [
            UpcomingRow(
                cliente=row.nome,
                cpf=row.cpf,
                vencimento=row.vencimento,
                valor=row.valor,
                parcela="—",
                crediario_id=row.crediario_id,
            )
            for row in rows
        ]


def late_clients(
    actor: SessionUser,
    order: str = "maior_valor_vencido",
    reference: date | None = None,
) -> list[LateRow]:
    _require_overview(actor)
    with session_scope() as session:
        rows = InstallmentRepository(session).late_by_client(reference, order)
        return [
            LateRow(
                cliente_id=row.id,
                cliente=row.nome,
                cpf=row.cpf,
                telefone=row.telefone,
                vencido=from_cents(row.vencido),
                saldo=from_cents(row.saldo),
                parcelas_vencidas=int(row.parcelas_vencidas or 0),
                vencimento_antigo=row.vencimento_antigo,
            )
            for row in rows
        ]


def client_overdue_summary(
    actor: SessionUser, client_id: int, reference: date | None = None
) -> tuple[Decimal, date | None, int]:
    """Valor vencido, vencimento mais antigo e quantidade — base do WhatsApp.

    É informação de cobrança (valor atrasado e dias de atraso), então segue a
    mesma regra do resto do módulo, mesmo sendo de um cliente só.
    """
    _require_overview(actor)
    with session_scope() as session:
        rows = InstallmentRepository(session).late_details(client_id, reference)
        if not rows:
            return ZERO, None, 0
        total = sum((row.valor for row in rows), ZERO)
        return total, rows[0].vencimento, len(rows)


def report(
    actor: SessionUser, inicio: date, fim: date, reference: date | None = None
) -> ReportData:
    _require_overview(actor)
    reference = reference or date.today()
    with session_scope() as session:
        sold = session.scalar(
            sa.select(sum_cents(Credit.valor_total)).where(
                Credit.criado_em.between(
                    datetime.combine(inicio, time.min), datetime.combine(fim, time.max)
                )
            )
        )
        received = PaymentRepository(session).total_period(inicio, fim)
        open_total = session.scalar(
            sa.select(sum_cents(Installment.valor)).where(Installment.pago.is_(False))
        )
        overdue_total = session.scalar(
            sa.select(sum_cents(Installment.valor)).where(
                Installment.pago.is_(False), Installment.vencimento < reference
            )
        )
        overdue_count = session.scalar(
            sa.select(sa.func.count(Installment.id)).where(
                Installment.pago.is_(False), Installment.vencimento < reference
            )
        )
        active = session.scalar(
            sa.select(sa.func.count(sa.distinct(Credit.cliente_id)))
            .select_from(Credit)
            .join(Installment, Installment.crediario_id == Credit.id)
            .where(Installment.pago.is_(False))
        )
        late = session.scalar(
            sa.select(sa.func.count(sa.distinct(Credit.cliente_id)))
            .select_from(Credit)
            .join(Installment, Installment.crediario_id == Credit.id)
            .where(Installment.pago.is_(False), Installment.vencimento < reference)
        )
        future = session.scalar(
            sa.select(sum_cents(Installment.valor)).where(
                Installment.pago.is_(False), Installment.vencimento >= reference
            )
        )

    return ReportData(
        inicio=inicio,
        fim=fim,
        total_vendido=from_cents(sold or 0),
        total_recebido=from_cents(received),
        total_a_receber=from_cents(open_total or 0),
        total_vencido=from_cents(overdue_total or 0),
        clientes_ativos=int(active or 0),
        clientes_em_atraso=int(late or 0),
        parcelas_vencidas=int(overdue_count or 0),
        vencimentos_futuros=from_cents(future or 0),
    )


def receivables_rows(
    actor: SessionUser, reference: date | None = None
) -> list[tuple[object, ...]]:
    """Linhas detalhadas de tudo que está em aberto (usado na exportação)."""
    _require_overview(actor)
    reference = reference or date.today()
    with session_scope() as session:
        stmt = (
            sa.select(
                Client.nome,
                Client.cpf,
                Client.telefone,
                Credit.id,
                Installment.numero,
                Credit.parcelas,
                Installment.vencimento,
                Installment.valor,
            )
            .select_from(Installment)
            .join(Credit, Credit.id == Installment.crediario_id)
            .join(Client, Client.id == Credit.cliente_id)
            .where(Installment.pago.is_(False))
            .order_by(Installment.vencimento)
        )
        rows = session.execute(stmt).all()

    result = []
    for row in rows:
        atraso = days_late(row.vencimento, reference)
        result.append(
            (
                row.nome,
                row.cpf,
                row.telefone,
                row.id,
                f"{row.numero}/{row.parcelas}",
                format_br(row.vencimento),
                format_brl(row.valor, symbol=False),
                "ATRASADO" if atraso else "EM ABERTO",
                atraso,
            )
        )
    return result


RECEIVABLES_HEADERS = (
    "Cliente",
    "CPF",
    "Telefone",
    "Crediário",
    "Parcela",
    "Vencimento",
    "Valor",
    "Situação",
    "Dias em atraso",
)

PAYMENTS_HEADERS = (
    "Data",
    "Cliente",
    "CPF",
    "Parcela",
    "Valor",
    "Crediário",
    "Identificador",
    "Usuário",
)

REVERSALS_HEADERS = (
    "Estornado em",
    "Cliente",
    "CPF",
    "Parcela",
    "Valor",
    "Data do pagamento",
    "Identificador",
    "Motivo",
    "Autorizado por",
)

SUMMARY_HEADERS = ("Indicador", "Valor")


def export_report(
    actor: SessionUser, path: Path, data: ReportData, fmt: str = "csv"
) -> Path:
    _require_overview(actor)
    return export(fmt, path, SUMMARY_HEADERS, data.as_rows())


def export_receivables(actor: SessionUser, path: Path, fmt: str = "csv") -> Path:
    return export(fmt, path, RECEIVABLES_HEADERS, receivables_rows(actor))


def reversals_rows(actor: SessionUser, inicio: date, fim: date) -> list[tuple[object, ...]]:
    """Linhas do relatório de estornos, na ordem dos cabeçalhos."""
    from app.services import payment_service

    _require_overview(actor)
    return [
        (
            format_datetime_br(item.data),
            item.cliente,
            item.cpf,
            item.parcela,
            format_brl(item.valor, symbol=False),
            format_br(item.data_pagamento),
            item.pagamento_codigo,
            item.motivo,
            item.usuario,
        )
        for item in payment_service.list_reversals(actor, inicio, fim)
    ]


def total_reversed(actor: SessionUser, inicio: date, fim: date) -> Decimal:
    """Valor total estornado no período — indicador de conferência do caixa."""
    _require_overview(actor)
    with session_scope() as session:
        return from_cents(ReversalRepository(session).total_period(inicio, fim))


def export_reversals(
    actor: SessionUser, path: Path, inicio: date, fim: date, fmt: str = "csv"
) -> Path:
    return export(fmt, path, REVERSALS_HEADERS, reversals_rows(actor, inicio, fim))


def export_payments(
    actor: SessionUser, path: Path, inicio: date, fim: date, fmt: str = "csv"
) -> Path:
    from app.services import payment_service

    _require_overview(actor)
    rows = [
        (
            format_br(item.data),
            item.cliente,
            item.cpf,
            item.parcela,
            format_brl(item.valor, symbol=False),
            item.crediario_id,
            item.codigo,
            item.usuario,
        )
        for item in payment_service.list_payments(inicio, fim, actor=actor)
    ]
    return export(fmt, path, PAYMENTS_HEADERS, rows)
