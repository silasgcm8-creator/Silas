"""Regras de negócio de crediários e geração de parcelas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import sqlalchemy as sa

from app.database.connection import session_scope
from app.models.credit import Credit
from app.models.installment import Installment
from app.models.log import LogAction
from app.models.status import InstallmentStatus
from app.repositories.client_repository import ClientRepository
from app.repositories.credit_repository import CreditRepository
from app.repositories.installment_repository import InstallmentRepository
from app.security.authentication import SessionUser
from app.security.permissions import Permission, require
from app.services import log_service
from app.services.errors import BusinessError, NotFoundError, ValidationError
from app.utils.dates import add_months
from app.utils.money import ZERO, format_brl, from_cents, split_installments, to_decimal
from app.utils.validators import validate_installment_count


@dataclass(frozen=True)
class InstallmentRow:
    id: int
    numero: int
    total: int
    vencimento: date
    valor: Decimal
    pago: bool
    pago_em: date | None
    status: str
    dias_atraso: int

    @property
    def rotulo(self) -> str:
        return f"{self.numero}/{self.total}"


@dataclass(frozen=True)
class CreditRow:
    id: int
    cliente_id: int
    cliente: str
    cpf: str
    telefone: str
    valor_total: Decimal
    entrada: Decimal
    parcelas: int
    pagas: int
    #: ``None`` quando quem pediu não tem a visão financeira — nesse caso o
    #: banco também não soma nada.
    saldo: Decimal | None
    vencido: Decimal | None
    criado_em: date | None


@dataclass(frozen=True)
class CreditDetail:
    id: int
    cliente_id: int
    cliente: str
    cpf: str
    telefone: str
    valor_total: Decimal
    entrada: Decimal
    financiado: Decimal
    parcelas: int
    primeiro_vencimento: date
    descricao: str | None
    criado_em: date | None
    installments: list[InstallmentRow]

    @property
    def total_pago(self) -> Decimal:
        return sum((i.valor for i in self.installments if i.pago), ZERO)

    @property
    def saldo(self) -> Decimal:
        return sum((i.valor for i in self.installments if not i.pago), ZERO)

    @property
    def vencido(self) -> Decimal:
        return sum((i.valor for i in self.installments if i.status == "ATRASADO"), ZERO)


def _status_sem_atraso(item: Installment, reference: date) -> str:
    """PAGO continua PAGO; vencida ou a vencer, tudo é ``EM ABERTO``."""
    situacao = item.status(reference)
    if situacao is InstallmentStatus.PAID:
        return situacao.value
    return InstallmentStatus.OPEN.value


def create_credit(
    cliente_id: int,
    valor_total: object,
    entrada: object,
    parcelas: object,
    primeiro_vencimento: date,
    descricao: str | None = None,
    actor: SessionUser | None = None,
) -> int:
    """Cria o crediário e gera todas as parcelas de uma só vez."""
    if actor:
        require(actor.role, Permission.CREDIT_CREATE)

    total = to_decimal(valor_total)
    down_payment = to_decimal(entrada)
    count = validate_installment_count(parcelas)

    if total <= ZERO:
        raise ValidationError("O valor total da compra deve ser maior que zero.")
    if down_payment < ZERO:
        raise ValidationError("A entrada não pode ser negativa.")
    if down_payment >= total:
        raise ValidationError("A entrada deve ser menor que o valor total da compra.")
    if not isinstance(primeiro_vencimento, date):
        raise ValidationError("Data do primeiro vencimento inválida.")

    financed = total - down_payment
    values = split_installments(financed, count)

    with session_scope() as session:
        client = ClientRepository(session).get(cliente_id)
        if client is None:
            raise NotFoundError("Selecione um cliente válido.")

        credit = Credit(
            cliente_id=cliente_id,
            valor_total=total,
            entrada=down_payment,
            parcelas=count,
            primeiro_vencimento=primeiro_vencimento,
            descricao=(descricao or "").strip() or None,
            criado_por_id=actor.id if actor else None,
        )
        session.add(credit)
        session.flush()

        for index, value in enumerate(values, start=1):
            session.add(
                Installment(
                    crediario_id=credit.id,
                    numero=index,
                    vencimento=add_months(primeiro_vencimento, index - 1),
                    valor=value,
                    pago=False,
                )
            )

        log_service.record(
            session,
            LogAction.CREDIT_CREATED,
            actor,
            detalhes=(
                f"{client.nome} — compra {format_brl(total)}, "
                f"entrada {format_brl(down_payment)}, {count}x"
            ),
            cliente_id=cliente_id,
            crediario_id=credit.id,
        )
        return credit.id


def list_credits(
    term: str = "", reference: date | None = None, actor: SessionUser | None = None
) -> list[CreditRow]:
    """Sem ``actor`` é chamada interna. Com ele, o perfil decide o que sai."""
    financeiro = actor is None or actor.can(Permission.FINANCE_OVERVIEW)
    with session_scope() as session:
        rows = CreditRepository(session).list_with_balances(
            term, reference, include_financials=financeiro
        )
        result: list[CreditRow] = []
        for row in rows:
            result.append(
                CreditRow(
                    id=row.id,
                    cliente_id=int(row.cliente_id),
                    cliente=row.nome,
                    cpf=row.cpf,
                    telefone=row.telefone,
                    valor_total=to_decimal(row.valor_total),
                    entrada=to_decimal(row.entrada),
                    parcelas=int(row.parcelas),
                    pagas=int(row.pagas or 0),
                    saldo=from_cents(row.saldo) if financeiro else None,
                    vencido=from_cents(row.vencido) if financeiro else None,
                    criado_em=row.criado_em.date() if row.criado_em else None,
                )
            )
        return result


def list_by_client(cliente_id: int, reference: date | None = None) -> list[dict[str, object]]:
    with session_scope() as session:
        rows = CreditRepository(session).list_by_client(cliente_id, reference)
        return [
            {
                "id": row.id,
                "valor_total": to_decimal(row.valor_total),
                "entrada": to_decimal(row.entrada),
                "parcelas": int(row.parcelas),
                "primeiro_vencimento": row.primeiro_vencimento,
                "saldo": from_cents(row.saldo),
                "pago": from_cents(row.pago),
                "vencido": from_cents(row.vencido),
                "criado_em": row.criado_em,
            }
            for row in rows
        ]


def delete_credit(credit_id: int, motivo: str, actor: SessionUser) -> str:
    """Apaga um crediário lançado por engano. Devolve o resumo do que saiu.

    A linha é simples e não se move: **só sai o que nunca movimentou dinheiro**.
    Se existe qualquer pagamento ligado ao crediário — inclusive um já estornado
    — a exclusão é recusada, porque a história do caixa não se apaga; o caminho
    ali é o estorno, que preserva o registro.

    Sem pagamento, não há nada de financeiro a preservar: o crediário sai de
    verdade do banco, levando junto parcelas e documentos de cobrança (o banco
    faz isso em cascata). O que fica é a trilha na auditoria — quem excluiu,
    quando, de qual cliente, por qual motivo.

    É esta exclusão que destrava também o cadastro do cliente: um cliente só é
    protegido contra exclusão enquanto tiver crediário.
    """
    require(actor.role, Permission.CREDIT_DELETE)
    motivo = " ".join((motivo or "").split())
    if len(motivo) < 5:
        raise ValidationError(
            "Informe o motivo da exclusão (no mínimo 5 caracteres). "
            "Ele fica registrado na auditoria."
        )

    from app.models.charge import ChargeDocument
    from app.models.payment import Payment

    with session_scope() as session:
        credit = CreditRepository(session).get_with_client(credit_id)
        if credit is None:
            raise NotFoundError("Crediário não encontrado.")

        pagamentos = session.scalar(
            sa.select(sa.func.count())
            .select_from(Payment)
            .where(Payment.crediario_id == credit_id)
        )
        if pagamentos:
            raise BusinessError(
                "Este crediário já teve pagamento registrado e não pode ser "
                "excluído. Para desfazer um recebimento, use o estorno — ele "
                "preserva o histórico."
            )

        documentos = int(
            session.scalar(
                sa.select(sa.func.count())
                .select_from(ChargeDocument)
                .where(ChargeDocument.crediario_id == credit_id)
            )
            or 0
        )

        cliente_nome = credit.client.nome
        cliente_id = credit.cliente_id
        resumo = (
            f"{cliente_nome} — crediário #{credit_id} de "
            f"{format_brl(credit.valor_total)} em {credit.parcelas}x"
        )
        detalhes = resumo + (
            f" (com {documentos} documento(s) de cobrança)" if documentos else ""
        ) + f" — motivo: {motivo}"

        # O log é gravado antes da remoção: depois dela o crediário não existe
        # mais para ser consultado, e a trilha precisa sobreviver.
        log_service.record(
            session,
            LogAction.CREDIT_DELETED,
            actor,
            detalhes=detalhes,
            cliente_id=cliente_id,
        )
        session.delete(credit)
        return resumo


def get_detail(
    credit_id: int, reference: date | None = None, actor: SessionUser | None = None
) -> CreditDetail:
    """Ficha do crediário com as parcelas.

    O funcionário precisa da lista para escolher qual parcela receber, então ela
    continua vindo inteira: número, vencimento, valor e se está paga. O que sai
    é o sinal de inadimplência — sem a visão financeira, uma parcela vencida
    aparece como ``EM ABERTO`` e sem dias de atraso.
    """
    reference = reference or date.today()
    atrasos = actor is None or actor.can(Permission.FINANCE_OVERVIEW)
    with session_scope() as session:
        credit = CreditRepository(session).get_with_client(credit_id)
        if credit is None:
            raise NotFoundError("Crediário não encontrado.")
        installments = InstallmentRepository(session).list_by_credit(credit_id)
        rows = [
            InstallmentRow(
                id=item.id,
                numero=item.numero,
                total=credit.parcelas,
                vencimento=item.vencimento,
                valor=item.valor,
                pago=item.pago,
                pago_em=item.pago_em,
                status=item.status(reference).value
                if atrasos
                else _status_sem_atraso(item, reference),
                dias_atraso=item.dias_atraso(reference) if atrasos else 0,
            )
            for item in installments
        ]
        return CreditDetail(
            id=credit.id,
            cliente_id=credit.cliente_id,
            cliente=credit.client.nome,
            cpf=credit.client.cpf,
            telefone=credit.client.telefone,
            valor_total=credit.valor_total,
            entrada=credit.entrada,
            financiado=credit.valor_financiado,
            parcelas=credit.parcelas,
            primeiro_vencimento=credit.primeiro_vencimento,
            descricao=credit.descricao,
            criado_em=credit.criado_em.date() if credit.criado_em else None,
            installments=rows,
        )


def find_installment(installment_id: int) -> tuple[CreditDetail, InstallmentRow]:
    """Localiza a parcela e o crediário a que ela pertence.

    Usado pelos documentos que tratam de uma parcela só (cobrança avulsa).
    """
    with session_scope() as session:
        installment = InstallmentRepository(session).get(installment_id)
        if installment is None:
            raise NotFoundError("Parcela não encontrada.")
        credit_id = installment.crediario_id

    detail = get_detail(credit_id)
    for item in detail.installments:
        if item.id == installment_id:
            return detail, item
    raise NotFoundError("Parcela não encontrada.")


def preview_installments(
    valor_total: object, entrada: object, parcelas: object, primeiro_vencimento: date
) -> list[tuple[int, date, Decimal]]:
    """Simulação usada na tela de novo crediário, antes de gravar."""
    total = to_decimal(valor_total)
    down_payment = to_decimal(entrada)
    count = validate_installment_count(parcelas)
    if total <= ZERO or down_payment >= total or down_payment < ZERO:
        raise ValidationError("Confira o valor da compra e da entrada.")
    values = split_installments(total - down_payment, count)
    return [
        (index, add_months(primeiro_vencimento, index - 1), value)
        for index, value in enumerate(values, start=1)
    ]
