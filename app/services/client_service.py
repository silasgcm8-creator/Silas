"""Regras de negócio de clientes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
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
from app.services.errors import BusinessError, DuplicateClientError, NotFoundError
from app.utils.cpf import only_digits
from app.utils.money import from_cents
from app.utils.validators import validate_cpf, validate_name, validate_phone


@dataclass(frozen=True)
class DeletedClientRow:
    """Cadastro excluído logicamente, com a trilha de quem excluiu."""

    id: int
    nome: str
    cpf: str
    telefone: str
    excluido_em: datetime | None
    excluido_por: str
    motivo: str


#: Formato do código interno mostrado ao cliente e digitado na busca.
CLIENT_CODE_WIDTH = 6


def client_code(client_id: int) -> str:
    """Código interno do cadastro: o `id` com zeros à esquerda (``000007``)."""
    return f"{client_id:0{CLIENT_CODE_WIDTH}d}"


@dataclass(frozen=True)
class RecentClientRow:
    """Cadastro recente para o terminal do balcão.

    Só dados operacionais: identificar e ligar para o cliente. Nenhum valor,
    nenhum saldo, nenhuma situação de pagamento — por construção, e não por
    filtro na tela.
    """

    id: int
    codigo: str
    nome: str
    telefone: str
    cadastrado_em: datetime | None


@dataclass(frozen=True)
class ClientRow:
    """Linha da tela de clientes.

    ``saldo`` e ``vencido`` vêm ``None`` para quem não tem a visão financeira:
    a informação não é omitida da tela, ela não sai do banco.
    """

    id: int
    nome: str
    cpf: str
    telefone: str
    saldo: Decimal | None
    vencido: Decimal | None
    crediarios: int


@dataclass(frozen=True)
class ClientSummary:
    """Ficha do cliente. Os totais só existem para a visão financeira."""

    id: int
    nome: str
    cpf: str
    telefone: str
    total_comprado: Decimal | None
    total_pago: Decimal | None
    total_aberto: Decimal | None
    total_vencido: Decimal | None

    @property
    def saldo_devedor(self) -> Decimal | None:
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
        # A busca inclui os excluídos: o CPF é único no banco inteiro, então
        # sem isso o cadastro repetido só falharia na restrição, com erro
        # técnico na tela em vez de uma orientação clara.
        existente = repo.get_by_cpf(cpf, include_deleted=True)
        if existente is not None:
            if existente.excluido:
                raise DuplicateClientError(
                    "Este CPF pertence a um cadastro excluído. Reative-o em "
                    "Clientes → Cadastros excluídos, em vez de cadastrar de novo."
                )
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


#: Tamanho da página das listagens. Segura o uso de memória e o tempo de
#: desenho da tabela em bases grandes.
PAGE_SIZE = 200


def list_clients(
    term: str = "",
    reference: date | None = None,
    limit: int = PAGE_SIZE,
    offset: int = 0,
    actor: SessionUser | None = None,
) -> list[ClientRow]:
    """Clientes ativos da busca.

    Sem ``actor`` a chamada é interna do próprio sistema e recebe tudo. Quando
    vem de uma tela ou de um endpoint, o perfil decide: sem a visão financeira,
    saldo e vencido não são nem calculados.
    """
    financeiro = actor is None or actor.can(Permission.FINANCE_OVERVIEW)
    with session_scope() as session:
        rows = ClientRepository(session).list_with_balances(
            term, reference, limit=limit, offset=offset, include_financials=financeiro
        )
        return [
            ClientRow(
                id=row.id,
                nome=row.nome,
                cpf=row.cpf,
                telefone=row.telefone,
                saldo=from_cents(row.saldo) if financeiro else None,
                vencido=from_cents(row.vencido) if financeiro else None,
                crediarios=int(row.crediarios or 0),
            )
            for row in rows
        ]


def recent_clients(limit: int = 8, actor: SessionUser | None = None) -> list[RecentClientRow]:
    """Últimos cadastros — o "CADASTROS RECENTES" do terminal do funcionário.

    Exige apenas a permissão de ver clientes; devolve exclusivamente nome,
    código, telefone e data. Nem para o administrador esta consulta traz
    dinheiro: quem quer números usa o painel.
    """
    if actor is not None:
        require(actor.role, Permission.CLIENT_VIEW)
    limit = max(1, min(int(limit), 50))
    with session_scope() as session:
        return [
            RecentClientRow(
                id=row.id,
                codigo=client_code(row.id),
                nome=row.nome,
                telefone=row.telefone,
                cadastrado_em=row.criado_em,
            )
            for row in ClientRepository(session).list_recent(limit)
        ]


def get_summary(
    client_id: int, reference: date | None = None, actor: SessionUser | None = None
) -> ClientSummary:
    """Ficha do cliente. Os totais só são somados para a visão financeira."""
    reference = reference or date.today()
    financeiro = actor is None or actor.can(Permission.FINANCE_OVERVIEW)
    with session_scope() as session:
        client = ClientRepository(session).get(client_id)
        if client is None:
            raise NotFoundError("Cliente não encontrado.")

        if not financeiro:
            # As somas nem chegam a ser consultadas: para receber uma parcela o
            # funcionário precisa do cadastro, não do histórico financeiro.
            return ClientSummary(
                id=client.id,
                nome=client.nome,
                cpf=client.cpf,
                telefone=client.telefone,
                total_comprado=None,
                total_pago=None,
                total_aberto=None,
                total_vencido=None,
            )

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


def delete_client(
    client_id: int, actor: SessionUser, confirm_cpf: str, motivo: str = ""
) -> None:
    """Exclusão **lógica**: exige administrador e confirmação do CPF.

    O cadastro sai das listas mas continua no banco, com autor, data e motivo.
    Nada é apagado de verdade, então a ação é reversível e auditável.

    Cliente com histórico financeiro continua protegido: nem lógica nem física.
    """
    require(actor.role, Permission.CLIENT_DELETE)
    with session_scope() as session:
        repo = ClientRepository(session)
        client = repo.get(client_id)
        if client is None or client.excluido:
            raise NotFoundError("Cliente não encontrado.")
        if repo.has_financial_history(client_id):
            raise DuplicateClientError(
                "Cliente possui histórico financeiro e não pode ser excluído. "
                "Mantenha o cadastro para preservar a auditoria."
            )
        if only_digits(confirm_cpf) != only_digits(client.cpf):
            raise NotFoundError("Confirmação incorreta: digite o CPF exato do cliente.")

        motivo = " ".join((motivo or "").split())[:300]
        client.excluido_em = datetime.now()
        client.excluido_por = actor.nome
        client.motivo_exclusao = motivo or None

        detalhes = f"{client.nome} — {client.cpf}"
        if motivo:
            detalhes += f" — motivo: {motivo}"
        log_service.record(
            session, LogAction.CLIENT_DELETED, actor, detalhes=detalhes, cliente_id=client_id
        )


def restore_client(client_id: int, actor: SessionUser) -> None:
    """Desfaz uma exclusão lógica — o cadastro volta às listas."""
    require(actor.role, Permission.CLIENT_DELETE)
    with session_scope() as session:
        client = ClientRepository(session).get(client_id)
        if client is None:
            raise NotFoundError("Cliente não encontrado.")
        if not client.excluido:
            raise BusinessError("Este cliente não está excluído.")
        client.excluido_em = None
        client.excluido_por = None
        client.motivo_exclusao = None
        log_service.record(
            session,
            LogAction.CLIENT_RESTORED,
            actor,
            detalhes=f"{client.nome} — {client.cpf}",
            cliente_id=client_id,
        )


def list_deleted(actor: SessionUser) -> list[DeletedClientRow]:
    """Cadastros excluídos, para o administrador conferir ou reativar."""
    require(actor.role, Permission.CLIENT_DELETE)
    with session_scope() as session:
        return [
            DeletedClientRow(
                id=client.id,
                nome=client.nome,
                cpf=client.cpf,
                telefone=client.telefone,
                excluido_em=client.excluido_em,
                excluido_por=client.excluido_por or "—",
                motivo=client.motivo_exclusao or "—",
            )
            for client in ClientRepository(session).list_deleted()
        ]


def total_clients() -> int:
    """Clientes ativos (excluídos logicamente não entram na contagem)."""
    with session_scope() as session:
        return ClientRepository(session).count_active()


def count_clients(term: str = "") -> int:
    """Quantos clientes atendem à busca, sem o limite da página."""
    with session_scope() as session:
        return ClientRepository(session).count_search(term)


def search_totals(
    actor: SessionUser, term: str = "", reference: date | None = None
) -> tuple[Decimal, Decimal]:
    """Saldo e vencido de todos os clientes da busca (não só da página).

    Somatório da carteira: com a busca vazia é o total a receber e o total
    vencido da loja inteira. Portanto, exclusivo do administrador.
    """
    require(actor.role, Permission.FINANCE_OVERVIEW)
    with session_scope() as session:
        saldo, vencido = ClientRepository(session).totals_search(term, reference)
        return from_cents(saldo), from_cents(vencido)


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
