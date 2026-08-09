"""Criação e versionamento leve do esquema."""

from __future__ import annotations

import logging

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.config import APP_VERSION, DB_SIGNATURE, SCHEMA_VERSION, settings
from app.database.connection import get_engine, session_scope
from app.models import Base  # noqa: F401  (importa todos os modelos)
from app.models.payment import UNIQUE_PAYMENT_INDEX
from app.models.setting import Setting

LOGGER = logging.getLogger("sys_crediario")

KEY_SIGNATURE = "app.signature"
KEY_SCHEMA = "app.schema_version"
KEY_VERSION = "app.version"
KEY_COMPANY = "empresa.nome"


def create_schema() -> None:
    Base.metadata.create_all(get_engine())


def _upsert(session: Session, key: str, value: str) -> None:
    row = session.get(Setting, key)
    if row is None:
        session.add(Setting(chave=key, valor=value))
    elif row.valor != value:
        row.valor = value


def seed_defaults() -> None:
    with session_scope() as session:
        _upsert(session, KEY_SIGNATURE, DB_SIGNATURE)
        _upsert(session, KEY_SCHEMA, str(SCHEMA_VERSION))
        _upsert(session, KEY_VERSION, APP_VERSION)
        if session.get(Setting, KEY_COMPANY) is None:
            session.add(Setting(chave=KEY_COMPANY, valor="SYS"))


def run_migrations() -> None:
    """Ponto único chamado na inicialização do programa."""
    settings.ensure_dirs()
    create_schema()
    seed_defaults()
    _apply_incremental_migrations()


def _deduplicate_payments() -> None:
    """Remove recebimentos repetidos da mesma parcela, mantendo o primeiro.

    Bancos criados antes do índice único podem ter dois recebimentos para uma
    única parcela (balcão e celular registrando ao mesmo tempo), o que inflava o
    caixa. A limpeza precisa vir antes da criação do índice, senão ele falha.
    """
    engine = get_engine()
    with engine.begin() as connection:
        removed = connection.execute(
            sa.text(
                "DELETE FROM pagamentos WHERE id NOT IN "
                "(SELECT MIN(id) FROM pagamentos GROUP BY parcela_id)"
            )
        ).rowcount
    if removed:
        LOGGER.warning(
            "Migração: %s recebimento(s) duplicado(s) removido(s) do caixa.", removed
        )


def _create_unique_payment_index() -> None:
    """Cria o índice único de pagamentos em bancos que ainda não o possuem."""
    engine = get_engine()
    existing = {index["name"] for index in sa.inspect(engine).get_indexes("pagamentos")}
    if UNIQUE_PAYMENT_INDEX in existing:
        return
    _deduplicate_payments()
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                f"CREATE UNIQUE INDEX {UNIQUE_PAYMENT_INDEX} ON pagamentos (parcela_id)"
            )
        )


def _apply_incremental_migrations() -> None:
    """Evoluções de esquema aplicadas em bancos já existentes."""
    _create_unique_payment_index()
    with session_scope() as session:
        row = session.get(Setting, KEY_SCHEMA)
        current = int(row.valor) if row and row.valor.isdigit() else 0
        if current < SCHEMA_VERSION and row is not None:
            row.valor = str(SCHEMA_VERSION)


def read_signature(engine: sa.Engine) -> str | None:
    """Lê a assinatura de um banco arbitrário (usado ao validar backups)."""
    inspector = sa.inspect(engine)
    if "configuracoes" not in inspector.get_table_names():
        return None
    with engine.connect() as connection:
        result = connection.execute(
            sa.text("SELECT valor FROM configuracoes WHERE chave = :k"),
            {"k": KEY_SIGNATURE},
        ).scalar()
    return str(result) if result is not None else None
