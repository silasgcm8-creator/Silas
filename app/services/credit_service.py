"""Regras de negócio de crediários e geração de parcelas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.database.connection import session_scope
from app.models.credit import Credit
from app.models.installment import Installment
from app.models.log import LogAction
from app.repositories.client_repository import ClientRepository
from app.repositories.credit_repository import CreditRepository
from app.repositories.installment_repository import InstallmentRepository
from app.security.authentication import SessionUser
from app.security.permissions import Permission, require
from app.services import log_service
from app.services.errors import NotFoundError, ValidationError
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
    saldo: Decimal
    vencido: Decimal
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


def list_credits(term: str = "", reference: date | None = None) -> list[CreditRow]:
    with session_scope() as session:
        rows = CreditRepository(session).list_with_balances(term, reference)
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
                    saldo=from_cents(row.saldo),
                    vencido=from_cents(row.vencido),
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


def get_detail(credit_id: int, reference: date | None = None) -> CreditDetail:
    reference = reference or date.today()
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
                status=item.status(reference).value,
                dias_atraso=item.dias_atraso(reference),
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
