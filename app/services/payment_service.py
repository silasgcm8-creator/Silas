"""Registro e estorno de pagamentos."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.database.connection import session_scope
from app.models.log import LogAction
from app.models.payment import Payment
from app.models.reversal import PaymentReversal
from app.repositories.credit_repository import CreditRepository
from app.repositories.installment_repository import InstallmentRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.reversal_repository import ReversalRepository
from app.security.authentication import SessionUser
from app.security.permissions import Permission, require
from app.services import log_service
from app.services.errors import BusinessError, NotFoundError
from app.utils.money import format_brl, from_cents
from app.utils.validators import validate_reversal_reason

ALREADY_PAID = "Esta parcela já está marcada como paga."


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
    codigo: str = ""
    parcela_id: int | None = None


@dataclass(frozen=True)
class ReversalRow:
    id: int
    data: datetime
    cliente: str
    cpf: str
    parcela: str
    valor: Decimal
    data_pagamento: date
    pagamento_codigo: str
    motivo: str
    usuario: str


def _build_code(payments: PaymentRepository, reference: date) -> str:
    """Identificador legível da operação: PAG-20260809-0007.

    Serve para o cliente e o balcão citarem o mesmo recebimento. A sequência é
    por dia; se houver colisão (duas origens no mesmo instante), completa com um
    sufixo aleatório em vez de falhar o pagamento.
    """
    sequence = payments.next_sequence_for_day(reference)
    codigo = f"PAG-{reference:%Y%m%d}-{sequence:04d}"
    if payments.get_by_code(codigo) is None:
        return codigo
    return f"PAG-{reference:%Y%m%d}-{secrets.token_hex(3).upper()}"


def mark_as_paid(
    installment_id: int,
    actor: SessionUser | None = None,
    payment_date: date | None = None,
) -> int:
    """Marca a parcela como paga e registra o recebimento no caixa.

    Tudo acontece em uma única transação: baixa da parcela, recebimento e log.
    Se qualquer etapa falhar, nada é gravado.

    Devolve o id do pagamento, usado para emitir o comprovante.
    """
    if actor:
        require(actor.role, Permission.PAYMENT_REGISTER)
    payment_date = payment_date or date.today()

    with session_scope() as session:
        installments = InstallmentRepository(session)
        installment = installments.get(installment_id)
        if installment is None:
            raise NotFoundError("Parcela não encontrada.")
        if installment.pago:
            raise BusinessError(ALREADY_PAID)

        credit = CreditRepository(session).get_with_client(installment.crediario_id)
        if credit is None:
            raise NotFoundError("Crediário não encontrado.")

        # Os dados do recebimento são copiados antes da baixa: depois dela o
        # estado da parcela em memória não é mais a fonte da verdade.
        numero, valor = installment.numero, installment.valor
        cliente_nome, total_parcelas = credit.client.nome, credit.parcelas
        credit_id, cliente_id = credit.id, credit.cliente_id

        # Baixa condicional: só uma origem consegue virar a parcela de aberta
        # para paga. Sem o `pago = False` no WHERE, balcão e celular operando
        # juntos registrariam dois recebimentos para a mesma parcela.
        if not installments.settle(installment_id, payment_date):
            raise BusinessError(ALREADY_PAID)

        payments = PaymentRepository(session)
        payment = Payment(
            parcela_id=installment_id,
            crediario_id=credit_id,
            cliente_id=cliente_id,
            valor=valor,
            data_pagamento=payment_date,
            codigo=_build_code(payments, payment_date),
            usuario_id=actor.id if actor else None,
            usuario_nome=actor.nome if actor else "sistema",
        )
        try:
            session.add(payment)
            session.flush()
        except IntegrityError as exc:
            # Rede de segurança do banco: o índice único de `parcela_id` barra
            # um segundo recebimento mesmo que a baixa acima tenha passado.
            raise BusinessError(ALREADY_PAID) from exc

        log_service.record(
            session,
            LogAction.INSTALLMENT_PAID,
            actor,
            detalhes=(
                f"{cliente_nome} — parcela {numero}/{total_parcelas}"
                f" de {format_brl(valor)} (recebimento {payment.codigo})"
            ),
            cliente_id=cliente_id,
            crediario_id=credit_id,
            parcela_id=installment_id,
        )
        return payment.id


def reverse_payment(
    installment_id: int, motivo: str, actor: SessionUser | None = None
) -> int:
    """Estorna um pagamento lançado por engano, com rastreabilidade completa.

    O pagamento **não é apagado**: ele é marcado como estornado e sai do caixa,
    e o motivo, o autor e o momento ficam registrados na tabela de estornos.
    A parcela volta para EM ABERTO ou ATRASADO conforme o vencimento.

    Devolve o id do estorno criado.
    """
    if actor:
        require(actor.role, Permission.PAYMENT_UNDO)
    motivo = validate_reversal_reason(motivo)

    with session_scope() as session:
        installments = InstallmentRepository(session)
        installment = installments.get(installment_id)
        if installment is None:
            raise NotFoundError("Parcela não encontrada.")
        if not installment.pago:
            raise BusinessError("Esta parcela não está paga.")

        payments = PaymentRepository(session)
        payment = payments.get_active_by_installment(installment_id)
        if payment is None:
            raise BusinessError(
                "Não há recebimento válido registrado para esta parcela."
            )

        credit = CreditRepository(session).get_with_client(installment.crediario_id)
        cliente_nome = credit.client.nome if credit else "—"

        installment.pago = False
        installment.pago_em = None

        agora = datetime.now()
        payment.estornado_em = agora
        reversal = PaymentReversal(
            pagamento_id=payment.id,
            parcela_id=installment_id,
            crediario_id=payment.crediario_id,
            cliente_id=payment.cliente_id,
            valor=payment.valor,
            data_pagamento=payment.data_pagamento,
            pagamento_codigo=payment.codigo,
            motivo=motivo,
            usuario_id=actor.id if actor else None,
            usuario_nome=actor.nome if actor else "sistema",
            criado_em=agora,
        )
        session.add(reversal)
        session.flush()

        log_service.record(
            session,
            LogAction.PAYMENT_REVERSED,
            actor,
            detalhes=(
                f"{cliente_nome} — parcela {installment.numero} de "
                f"{format_brl(payment.valor)} (recebimento {payment.codigo}) — "
                f"motivo: {motivo}"
            ),
            cliente_id=payment.cliente_id,
            crediario_id=payment.crediario_id,
            parcela_id=installment_id,
        )
        return reversal.id


def list_reversals(start: date, end: date) -> list[ReversalRow]:
    """Estornos do período, para a auditoria e o relatório de estornos."""
    with session_scope() as session:
        return [
            ReversalRow(
                id=row.id,
                data=row.criado_em,
                cliente=row.nome,
                cpf=row.cpf,
                parcela=f"{row.numero}/{row.parcelas}",
                valor=row.valor,
                data_pagamento=row.data_pagamento,
                pagamento_codigo=row.pagamento_codigo,
                motivo=row.motivo,
                usuario=row.usuario_nome or "—",
            )
            for row in ReversalRepository(session).list_period(start, end)
        ]


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
                codigo=row.codigo,
                parcela_id=row.parcela_id,
            )
            for row in rows
        ]


def total_received(start: date, end: date) -> Decimal:
    with session_scope() as session:
        return from_cents(PaymentRepository(session).total_period(start, end))
