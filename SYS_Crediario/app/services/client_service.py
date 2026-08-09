"""Regras de negócio de clientes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import sqlalchemy as sa

from app.database.connection import session_scope
from app.database.types import sum_cents
from app.models.client import Client
from app.models.credit import Credit
from app.models.installment import Installment
from app.models.log import LogAction
from app.repositories.client_repository import ClientRepository
from app.security.authentication import SessionUser
from app.security.permissions import Permission, require
from app.services import log_service
from app.services.errors import DuplicateClientError, NotFoundError
from app.utils.cpf import only_digits
from app.utils.money import from_cents
from app.utils.validators import validate_cpf, validate_name, validate_phone


@dataclass(frozen=True)
class ClientRow:
    """Linha da tela de clientes."""

    id: int
    nome: str
    cpf: str
    telefone: str
    saldo: Decimal
    vencido: Decimal
    crediarios: int


@dataclass(frozen=True)
class ClientSummary:
    """Ficha financeira consolidada do cliente."""

    id: int
    nome: str
    cpf: str
    telefone: str
    total_comprado: Decimal
    total_pago: Decimal
    total_aberto: Decimal
    total_vencido: Decimal

    @property
    def saldo_devedor(self) -> Decimal:
        return self.total_aberto


def create_client(
    nome: str, cpf: str, telefone: str, actor: SessionUser | None = None
) -> int:
    if actor:
        require(actor.role, Permission.CLIENT_CREATE)
    nome = validate_name(nome)
    cpf = validate_cpf(cpf)
    telefone = validate_phone(telefone)

    with session_scope() as session:
        repo = ClientRepository(session)
        if repo.get_by_cpf(cpf) is not None:
            raise DuplicateClientError(
                "Este CPF já está cadastrado. Pesquise o cliente na tela Clientes."
            )
        client = repo.add(Client(nome=nome, cpf=cpf, telefone=telefone))
        log_service.record(
            session,
            LogAction.CLIENT_CREATED,
            actor,
            detalhes=f"{nome} — {cpf}",
            cliente_id=client.id,
        )
        return client.id


def update_client(
    client_id: int, nome: str, telefone: str, actor: SessionUser | None = None
) -> None:
    """Nome e telefone podem ser corrigidos; o CPF é imutável."""
    if actor:
        require(actor.role, Permission.CLIENT_EDIT)
    nome = validate_name(nome)
    telefone = validate_phone(telefone)

    with session_scope() as session:
        repo = ClientRepository(session)
        client = repo.get(client_id)
        if client is None:
            raise NotFoundError("Cliente não encontrado.")
        antes = f"{client.nome} / {client.telefone}"
        client.nome = nome
        client.telefone = telefone
        log_service.record(
            session,
            LogAction.CLIENT_UPDATED,
            actor,
            detalhes=f"{antes} → {nome} / {telefone}",
            cliente_id=client.id,
        )


def get_client(client_id: int) -> Client:
    with session_scope() as session:
        client = ClientRepository(session).get(client_id)
        if client is None:
            raise NotFoundError("Cliente não encontrado.")
        session.expunge(client)
        return client


def find_by_cpf(cpf: str) -> Client | None:
    with session_scope() as session:
        client = ClientRepository(session).get_by_cpf(cpf)
        if client is not None:
            session.expunge(client)
        return client


def list_clients(term: str = "", reference: date | None = None) -> list[ClientRow]:
    with session_scope() as session:
        rows = ClientRepository(session).list_with_balances(term, reference)
        return [
            ClientRow(
                id=row.id,
                nome=row.nome,
                cpf=row.cpf,
                telefone=row.telefone,
                saldo=from_cents(row.saldo),
                vencido=from_cents(row.vencido),
                crediarios=int(row.crediarios or 0),
            )
            for row in rows
        ]


def get_summary(client_id: int, reference: date | None = None) -> ClientSummary:
    reference = reference or date.today()
    with session_scope() as session:
        client = ClientRepository(session).get(client_id)
        if client is None:
            raise NotFoundError("Cliente não encontrado.")

        paid = sa.case((Installment.pago.is_(True), Installment.valor), else_=0)
        open_value = sa.case((Installment.pago.is_(False), Installment.valor), else_=0)
        overdue = sa.case(
            (
                sa.and_(Installment.pago.is_(False), Installment.vencimento < reference),
                Installment.valor,
            ),
            else_=0,
        )
        stmt = (
            sa.select(
                sum_cents(paid).label("pago"),
                sum_cents(open_value).label("aberto"),
                sum_cents(overdue).label("vencido"),
            )
            .select_from(Credit)
            .outerjoin(Installment, Installment.crediario_id == Credit.id)
            .where(Credit.cliente_id == client_id)
        )
        totals = session.execute(stmt).one()

        bought = session.scalar(
            sa.select(sum_cents(Credit.valor_total)).where(Credit.cliente_id == client_id)
        )
        entrada = session.scalar(
            sa.select(sum_cents(Credit.entrada)).where(Credit.cliente_id == client_id)
        )

        return ClientSummary(
            id=client.id,
            nome=client.nome,
            cpf=client.cpf,
            telefone=client.telefone,
            total_comprado=from_cents(bought or 0),
            total_pago=from_cents(totals.pago) + from_cents(entrada or 0),
            total_aberto=from_cents(totals.aberto),
            total_vencido=from_cents(totals.vencido),
        )


def can_delete(client_id: int) -> bool:
    with session_scope() as session:
        return not ClientRepository(session).has_financial_history(client_id)


def delete_client(client_id: int, actor: SessionUser, confirm_cpf: str) -> None:
    """Exclusão administrativa: exige administrador e confirmação do CPF.

    Cliente com histórico financeiro nunca é excluído de forma simples.
    """
    require(actor.role, Permission.CLIENT_DELETE)
    with session_scope() as session:
        repo = ClientRepository(session)
        client = repo.get(client_id)
        if client is None:
            raise NotFoundError("Cliente não encontrado.")
        if repo.has_financial_history(client_id):
            raise DuplicateClientError(
                "Cliente possui histórico financeiro e não pode ser excluído. "
                "Mantenha o cadastro para preservar a auditoria."
            )
        if only_digits(confirm_cpf) != only_digits(client.cpf):
            raise NotFoundError("Confirmação incorreta: digite o CPF exato do cliente.")
        detalhes = f"{client.nome} — {client.cpf}"
        repo.delete(client)
        log_service.record(
            session, LogAction.CLIENT_DELETED, actor, detalhes=detalhes, cliente_id=client_id
        )


def total_clients() -> int:
    with session_scope() as session:
        return ClientRepository(session).count()


def active_clients(reference: date | None = None) -> int:
    """Clientes com pelo menos uma parcela em aberto."""
    reference = reference or date.today()
    with session_scope() as session:
        stmt = (
            sa.select(sa.func.count(sa.distinct(Credit.cliente_id)))
            .select_from(Credit)
            .join(Installment, Installment.crediario_id == Credit.id)
            .where(Installment.pago.is_(False))
        )
        return int(session.scalar(stmt) or 0)
