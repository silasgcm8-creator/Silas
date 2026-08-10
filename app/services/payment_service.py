"""Registro e estorno de pagamentos."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.database.connection import session_scope
from app.models.charge import ChargeDocument
from app.models.credit import Credit
from app.models.installment import Installment
from app.models.log import LogAction
from app.models.payment import Payment
from app.models.reversal import PaymentReversal
from app.models.status import PaymentMethod, payment_method_label
from app.repositories.credit_repository import CreditRepository
from app.repositories.installment_repository import InstallmentRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.reversal_repository import ReversalRepository
from app.security.authentication import SessionUser
from app.security.permissions import Permission, require
from app.services import log_service
from app.services.errors import BusinessError, NotFoundError, ValidationError
from app.utils.money import ZERO, format_brl, from_cents
from app.utils.validators import validate_payment_note, validate_reversal_reason

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
    forma: str = ""
    documento_id: int | None = None


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


def _validate_charge(
    session, documento_id: int | None, installment_id: int
) -> ChargeDocument | None:  # noqa: ANN001 - Session concreta do chamador
    """Confere que o documento informado é mesmo desta parcela e vale hoje.

    Antes de o valor do recebimento vir do documento, um `documento_id` errado
    era só um vínculo torto no histórico. Agora ele define quanto entra no
    caixa, então precisa ser conferido: existe, é desta parcela e não foi
    cancelado.
    """
    if documento_id is None:
        return None
    documento = session.get(ChargeDocument, documento_id)
    if documento is None:
        raise NotFoundError("Documento de cobrança não encontrado.")
    if documento.parcela_id != installment_id:
        raise BusinessError(
            "O documento de cobrança informado é de outra parcela. "
            "Selecione a parcela correspondente ao documento."
        )
    if documento.cancelado_em is not None:
        raise BusinessError(
            "Este documento de cobrança foi cancelado. Emita um novo antes de "
            "registrar o recebimento."
        )
    return documento


def mark_as_paid(
    installment_id: int,
    actor: SessionUser | None = None,
    payment_date: date | None = None,
    forma_pagamento: str = "",
    documento_id: int | None = None,
    observacao: str = "",
) -> int:
    """Marca a parcela como paga e registra o recebimento no caixa.

    Tudo acontece em uma única transação: baixa da parcela, recebimento e log.
    Se qualquer etapa falhar, nada é gravado.

    A data do recebimento não pode ser futura: o caixa registra o que já
    entrou, e uma data adiante desmontaria o fechamento do dia.

    Devolve o id do pagamento, usado para emitir o comprovante.
    """
    if actor:
        require(actor.role, Permission.PAYMENT_REGISTER)
    payment_date = payment_date or date.today()
    if payment_date > date.today():
        raise ValidationError(
            "A data do recebimento não pode ser futura — registre o dia em que "
            "o dinheiro entrou."
        )
    forma = PaymentMethod.from_value(forma_pagamento).value if forma_pagamento else ""
    observacao = validate_payment_note(observacao)

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

        # O que entra no caixa é o que o cliente pagou. Com documento de
        # cobrança, é o valor impresso nele (parcela + juros − desconto), não o
        # valor de face da parcela: quem paga um boleto de R$ 330 não deposita
        # R$ 300. A parcela continua quitada pelo valor dela — são coisas
        # diferentes: quanto da dívida foi liquidada e quanto dinheiro entrou.
        documento = _validate_charge(session, documento_id, installment_id)
        valor_recebido = documento.valor_atualizado if documento else valor
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
            valor=valor_recebido,
            data_pagamento=payment_date,
            codigo=_build_code(payments, payment_date),
            forma_pagamento=forma,
            documento_id=documento_id,
            observacao=observacao,
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
                f" de {format_brl(valor_recebido)} (recebimento {payment.codigo}"
                + (f", {payment_method_label(forma)}" if forma else "")
                + ")"
                # Quando o documento traz juros ou desconto, o log guarda a
                # composição: sem isso, o valor no caixa não bate com a parcela
                # e ninguém consegue explicar a diferença meses depois.
                + (
                    f" — parcela {format_brl(valor)}"
                    + (f" + juros {format_brl(documento.juros)}" if documento.juros > ZERO else "")
                    + (
                        f" − desconto {format_brl(documento.desconto)}"
                        if documento.desconto > ZERO
                        else ""
                    )
                    + f" (documento {documento.numero})"
                    if documento is not None and valor_recebido != valor
                    else ""
                )
                + (f" — obs.: {observacao}" if observacao else "")
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


@dataclass(frozen=True)
class PayableRow:
    """Parcela em aberto de **um** cliente, pronta para receber.

    Contrato estreito de propósito: o que o caixa precisa para identificar a
    parcela e conferir o valor. Sem situação de atraso, sem dias em atraso, sem
    saldo do cliente — registrar um recebimento não é consultar inadimplência.
    """

    parcela_id: int
    crediario_id: int
    parcela: str
    vencimento: date
    #: Valor de face da parcela — o que ela abate da dívida.
    valor_parcela: Decimal
    #: O que o cliente paga hoje. Com documento de cobrança é o valor impresso
    #: nele (parcela + juros − desconto); sem documento, é a própria parcela.
    #: A tela mostra este, e é este que entra no caixa.
    valor_a_receber: Decimal
    #: Número da cobrança ativa da parcela, quando o cliente chegou com ela.
    documento: str | None
    documento_id: int | None

    @property
    def tem_ajuste(self) -> bool:
        return self.valor_a_receber != self.valor_parcela


def payable_for_client(client_id: int, actor: SessionUser) -> list[PayableRow]:
    """Parcelas em aberto do cliente, da mais antiga para a mais nova."""
    require(actor.role, Permission.PAYMENT_REGISTER)
    with session_scope() as session:
        ativo = ChargeDocument.cancelado_em.is_(None)
        stmt = (
            sa.select(
                Installment.id,
                Installment.numero,
                Installment.vencimento,
                Installment.valor,
                Credit.id.label("crediario_id"),
                Credit.parcelas,
                ChargeDocument.id.label("documento_id"),
                ChargeDocument.numero.label("documento"),
                ChargeDocument.valor_atualizado,
            )
            .select_from(Installment)
            .join(Credit, Credit.id == Installment.crediario_id)
            .outerjoin(
                ChargeDocument,
                sa.and_(ChargeDocument.parcela_id == Installment.id, ativo),
            )
            .where(Credit.cliente_id == client_id, Installment.pago.is_(False))
            .order_by(Installment.vencimento, Installment.id)
        )
        return [
            PayableRow(
                parcela_id=row.id,
                crediario_id=row.crediario_id,
                parcela=f"{row.numero:02d}/{row.parcelas:02d}",
                vencimento=row.vencimento,
                valor_parcela=row.valor,
                valor_a_receber=(
                    row.valor_atualizado if row.documento_id is not None else row.valor
                ),
                documento=row.documento,
                documento_id=row.documento_id,
            )
            for row in session.execute(stmt).all()
        ]


def list_reversals(actor: SessionUser, start: date, end: date) -> list[ReversalRow]:
    """Estornos do período, para a auditoria e o relatório de estornos."""
    require(actor.role, Permission.FINANCE_OVERVIEW)
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


def list_payments(
    start: date, end: date, term: str = "", *, actor: SessionUser
) -> list[PaymentRow]:
    """Recebimentos do período, no limite do que o solicitante pode ver.

    Administrador vê o caixa inteiro. O funcionário vê **apenas os recebimentos
    que ele mesmo registrou** — o suficiente para conferir a própria operação e
    reimprimir um comprovante, sem revelar o movimento financeiro da loja.
    """
    escopo = None if actor.can(Permission.FINANCE_OVERVIEW) else actor.id
    with session_scope() as session:
        rows = PaymentRepository(session).list_period(
            start, end, term, usuario_id=escopo
        )
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
                forma=payment_method_label(row.forma_pagamento),
                documento_id=row.documento_id,
            )
            for row in rows
        ]


def total_received(start: date, end: date, *, actor: SessionUser) -> Decimal:
    """Total recebido pela loja no período — número consolidado, só do dono."""
    require(actor.role, Permission.FINANCE_OVERVIEW)
    with session_scope() as session:
        return from_cents(PaymentRepository(session).total_period(start, end))
