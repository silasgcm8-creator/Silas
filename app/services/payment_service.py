"""Registro e estorno de pagamentos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.database.connection import session_scope
from app.models.log import LogAction
from app.models.payment import Payment
from app.repositories.credit_repository import CreditRepository
from app.repositories.installment_repository import InstallmentRepository
from app.repositories.payment_repository import PaymentRepository
from app.security.authentication import SessionUser
from app.security.permissions import Permission, require
from app.services import log_service
from app.services.errors import BusinessError, NotFoundError
from app.utils.money import format_brl, from_cents


@dataclass(frozen=True)
class PaymentRow:
    id: int
    data: date
    cliente: str
    cpf: str
    parcela: str
    valor: Decimal
    crediario_id: int
    usuario: str


def mark_as_paid(
    installment_id: int,
    actor: SessionUser | None = None,
    payment_date: date | None = None,
) -> None:
    """Marca a parcela como paga e registra o recebimento no caixa."""
    if actor:
        require(actor.role, Permission.PAYMENT_REGISTER)
    payment_date = payment_date or date.today()

    with session_scope() as session:
        installments = InstallmentRepository(session)
        installment = installments.get(installment_id)
        if installment is None:
            raise NotFoundError("Parcela não encontrada.")
        if installment.pago:
            raise BusinessError("Esta parcela já está marcada como paga.")

        credit = CreditRepository(session).get_with_client(installment.crediario_id)
        if credit is None:
            raise NotFoundError("Crediário não encontrado.")

        installment.pago = True
        installment.pago_em = payment_date

        session.add(
            Payment(
                parcela_id=installment.id,
                crediario_id=credit.id,
                cliente_id=credit.cliente_id,
                valor=installment.valor,
                data_pagamento=payment_date,
                usuario_id=actor.id if actor else None,
                usuario_nome=actor.nome if actor else "sistema",
            )
        )

        log_service.record(
            session,
            LogAction.INSTALLMENT_PAID,
            actor,
            detalhes=(
                f"{credit.client.nome} — parcela {installment.numero}/{credit.parcelas}"
                f" de {format_brl(installment.valor)}"
            ),
            cliente_id=credit.cliente_id,
            crediario_id=credit.id,
            parcela_id=installment.id,
        )


def undo_payment(installment_id: int, actor: SessionUser | None = None) -> None:
    """Desfaz um pagamento lançado por engano.

    A parcela volta automaticamente para EM ABERTO ou ATRASADO conforme a data
    de vencimento, e o recebimento sai do caixa.
    """
    if actor:
        require(actor.role, Permission.PAYMENT_UNDO)

    with session_scope() as session:
        installments = InstallmentRepository(session)
        installment = installments.get(installment_id)
        if installment is None:
            raise NotFoundError("Parcela não encontrada.")
        if not installment.pago:
            raise BusinessError("Esta parcela não está paga.")

        credit = CreditRepository(session).get_with_client(installment.crediario_id)
        installment.pago = False
        installment.pago_em = None
        PaymentRepository(session).delete_by_installment(installment_id)

        log_service.record(
            session,
            LogAction.PAYMENT_UNDONE,
            actor,
            detalhes=(
                f"{credit.client.nome if credit else '—'} — parcela {installment.numero}"
                f" de {format_brl(installment.valor)}"
            ),
            cliente_id=credit.cliente_id if credit else None,
            crediario_id=installment.crediario_id,
            parcela_id=installment.id,
        )


def list_payments(start: date, end: date, term: str = "") -> list[PaymentRow]:
    with session_scope() as session:
        rows = PaymentRepository(session).list_period(start, end, term)
        return [
            PaymentRow(
                id=row.id,
                data=row.data_pagamento,
                cliente=row.nome,
                cpf=row.cpf,
                parcela=f"{row.numero}/{row.parcelas}",
                valor=row.valor,
                crediario_id=row.crediario_id,
                usuario=row.usuario_nome or "—",
            )
            for row in rows
        ]


def total_received(start: date, end: date) -> Decimal:
    with session_scope() as session:
        return from_cents(PaymentRepository(session).total_period(start, end))
