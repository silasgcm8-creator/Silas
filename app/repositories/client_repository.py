"""Consultas de clientes."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa

from app.database.types import sum_cents
from app.models.client import Client
from app.models.credit import Credit
from app.models.installment import Installment
from app.repositories.base_repository import BaseRepository
from app.utils.cpf import only_digits


def _digits_expr(column):  # noqa: ANN001, ANN201
    """Remove máscara de uma coluna diretamente no SQL para busca por dígitos."""
    expr = column
    for token in (".", "-", " ", "(", ")", "+"):
        expr = sa.func.replace(expr, token, "")
    return expr


def client_search_filter(term: str):  # noqa: ANN201
    """Filtro único de busca por nome, CPF ou telefone (com ou sem máscara)."""
    term = (term or "").strip()
    if not term:
        return None
    like = f"%{term}%"
    conditions = [Client.nome.ilike(like), Client.cpf.like(like), Client.telefone.like(like)]
    digits = only_digits(term)
    if digits:
        digits_like = f"%{digits}%"
        conditions.append(_digits_expr(Client.cpf).like(digits_like))
        conditions.append(_digits_expr(Client.telefone).like(digits_like))
    return sa.or_(*conditions)


#: Cliente ativo é o que não foi excluído logicamente. Aplicado em todas as
#: listagens: o cadastro excluído não some do banco, apenas das telas.
ACTIVE = Client.excluido_em.is_(None)


class ClientRepository(BaseRepository[Client]):
    model = Client

    def get_by_cpf(self, cpf: str, include_deleted: bool = False) -> Client | None:
        """Busca pelo CPF. O CPF é único mesmo entre excluídos, então a checagem
        de duplicidade precisa enxergar o cadastro excluído para poder reativá-lo."""
        digits = only_digits(cpf)
        stmt = sa.select(Client).where(
            sa.func.replace(
                sa.func.replace(sa.func.replace(Client.cpf, ".", ""), "-", ""), " ", ""
            )
            == digits
        )
        if not include_deleted:
            stmt = stmt.where(ACTIVE)
        return self.session.scalars(stmt).first()

    def search(self, term: str = "", limit: int = 500) -> Sequence[Client]:
        stmt = sa.select(Client).where(ACTIVE).order_by(Client.nome)
        condition = client_search_filter(term)
        if condition is not None:
            stmt = stmt.where(condition)
        return self.session.scalars(stmt.limit(limit)).all()

    def count_search(self, term: str = "") -> int:
        """Quantos clientes atendem à busca, ignorando o limite da página.

        É o que permite avisar "mostrando 500 de 12.340" em vez de truncar a
        lista em silêncio.
        """
        stmt = sa.select(sa.func.count(Client.id)).where(ACTIVE)
        condition = client_search_filter(term)
        if condition is not None:
            stmt = stmt.where(condition)
        return int(self.session.scalar(stmt) or 0)

    def count_active(self) -> int:
        return int(self.session.scalar(sa.select(sa.func.count(Client.id)).where(ACTIVE)) or 0)

    def list_deleted(self, limit: int = 200) -> Sequence[Client]:
        stmt = (
            sa.select(Client)
            .where(Client.excluido_em.is_not(None))
            .order_by(Client.excluido_em.desc())
            .limit(limit)
        )
        return self.session.scalars(stmt).all()

    def list_with_balances(
        self,
        term: str = "",
        reference: date | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> Sequence[sa.Row]:
        """Clientes com saldo devedor e valor vencido calculados no banco."""
        reference = reference or date.today()
        open_value = sa.case((Installment.pago.is_(False), Installment.valor), else_=0)
        overdue_value = sa.case(
            (
                sa.and_(Installment.pago.is_(False), Installment.vencimento < reference),
                Installment.valor,
            ),
            else_=0,
        )
        stmt = (
            sa.select(
                Client.id,
                Client.nome,
                Client.cpf,
                Client.telefone,
                sum_cents(open_value).label("saldo"),
                sum_cents(overdue_value).label("vencido"),
                sa.func.count(sa.distinct(Credit.id)).label("crediarios"),
            )
            .select_from(Client)
            .outerjoin(Credit, Credit.cliente_id == Client.id)
            .outerjoin(Installment, Installment.crediario_id == Credit.id)
            .where(ACTIVE)
            .group_by(Client.id)
            .order_by(Client.nome)
            .limit(limit)
            .offset(offset)
        )
        condition = client_search_filter(term)
        if condition is not None:
            stmt = stmt.where(condition)
        return self.session.execute(stmt).all()

    def totals_search(
        self, term: str = "", reference: date | None = None
    ) -> tuple[int, int]:
        """Saldo e vencido somados sobre **todos** os clientes da busca.

        Calculado no banco, não na página: com paginação, somar só as linhas
        exibidas daria um total errado na tela.
        """
        reference = reference or date.today()
        open_value = sa.case((Installment.pago.is_(False), Installment.valor), else_=0)
        overdue_value = sa.case(
            (
                sa.and_(Installment.pago.is_(False), Installment.vencimento < reference),
                Installment.valor,
            ),
            else_=0,
        )
        stmt = (
            sa.select(
                sum_cents(open_value).label("saldo"),
                sum_cents(overdue_value).label("vencido"),
            )
            .select_from(Client)
            .outerjoin(Credit, Credit.cliente_id == Client.id)
            .outerjoin(Installment, Installment.crediario_id == Credit.id)
            .where(ACTIVE)
        )
        condition = client_search_filter(term)
        if condition is not None:
            stmt = stmt.where(condition)
        row = self.session.execute(stmt).first()
        return (int(row.saldo or 0), int(row.vencido or 0)) if row else (0, 0)

    def has_financial_history(self, client_id: int) -> bool:
        stmt = sa.select(sa.func.count()).select_from(Credit).where(
            Credit.cliente_id == client_id
        )
        return int(self.session.scalar(stmt) or 0) > 0
