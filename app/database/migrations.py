"""Criação e versionamento leve do esquema."""

from __future__ import annotations

import logging

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.config import APP_VERSION, DB_SIGNATURE, SCHEMA_VERSION, settings
from app.database.connection import get_engine, session_scope
from app.models import Base  # noqa: F401  (importa todos os modelos)
from app.models.payment import ACTIVE_PAYMENT_CONDITION, UNIQUE_PAYMENT_INDEX
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


#: Colunas acrescentadas por versões novas, por tabela.
NEW_COLUMNS: dict[str, dict[str, str]] = {
    "pagamentos": {
        "codigo": "VARCHAR(24) DEFAULT ''",
        "estornado_em": "DATETIME",
    },
    "clientes": {
        "excluido_em": "DATETIME",
        "excluido_por": "VARCHAR(120)",
        "motivo_exclusao": "VARCHAR(300)",
    },
}


def _add_missing_columns() -> None:
    """Acrescenta colunas novas sem tocar nos dados já gravados."""
    engine = get_engine()
    inspector = sa.inspect(engine)
    for tabela, novas in NEW_COLUMNS.items():
        existing = {column["name"] for column in inspector.get_columns(tabela)}
        for nome, definicao in novas.items():
            if nome in existing:
                continue
            with engine.begin() as connection:
                connection.execute(
                    sa.text(f"ALTER TABLE {tabela} ADD COLUMN {nome} {definicao}")
                )
            LOGGER.info("Migração: coluna %s.%s criada.", tabela, nome)


def _backfill_payment_codes() -> None:
    """Dá um identificador aos recebimentos gravados antes do código existir."""
    engine = get_engine()
    with engine.begin() as connection:
        pendentes = connection.execute(
            sa.text(
                "SELECT id, data_pagamento FROM pagamentos "
                "WHERE codigo IS NULL OR codigo = ''"
            )
        ).all()
        for row in pendentes:
            dia = str(row.data_pagamento or "")[:10].replace("-", "") or "00000000"
            connection.execute(
                sa.text("UPDATE pagamentos SET codigo = :codigo WHERE id = :id"),
                {"codigo": f"PAG-{dia}-{row.id:04d}", "id": row.id},
            )
    if pendentes:
        LOGGER.info("Migração: %s recebimento(s) receberam código.", len(pendentes))


def _payment_index_definition() -> str | None:
    """Texto da definição do índice único, ou None se ele não existir."""
    engine = get_engine()
    dialect = engine.dialect.name
    if dialect == "sqlite":
        query = "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = :nome"
    elif dialect == "postgresql":
        query = "SELECT indexdef FROM pg_indexes WHERE indexname = :nome"
    else:  # pragma: no cover - outros bancos não são suportados hoje
        names = {i["name"] for i in sa.inspect(engine).get_indexes("pagamentos")}
        return "" if UNIQUE_PAYMENT_INDEX in names else None
    with engine.connect() as connection:
        found = connection.execute(
            sa.text(query), {"nome": UNIQUE_PAYMENT_INDEX}
        ).first()
    if found is None:
        return None
    return str(found[0] or "")


def _create_unique_payment_index() -> None:
    """Garante o índice único **parcial** de recebimento por parcela.

    Bancos da versão anterior têm o índice sem condição, o que impediria a
    parcela de ser paga de novo depois de um estorno. Nesse caso o índice é
    recriado com a condição `estornado_em IS NULL`.
    """
    engine = get_engine()
    definition = _payment_index_definition()
    if definition is not None and "estornado_em" in definition:
        return

    if definition is not None:
        with engine.begin() as connection:
            connection.execute(sa.text(f"DROP INDEX {UNIQUE_PAYMENT_INDEX}"))
        LOGGER.info("Migração: índice de recebimento recriado com condição.")

    _deduplicate_payments()
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                f"CREATE UNIQUE INDEX {UNIQUE_PAYMENT_INDEX} ON pagamentos "
                f"(parcela_id) WHERE {ACTIVE_PAYMENT_CONDITION}"
            )
        )


def _apply_incremental_migrations() -> None:
    """Evoluções de esquema aplicadas em bancos já existentes.

    A ordem importa: as colunas precisam existir antes do índice que depende
    delas, e a limpeza de duplicados antes da criação do índice único.
    """
    _add_missing_columns()
    _backfill_payment_codes()
    _create_unique_payment_index()
    with session_scope() as session:
        row = session.get(Setting, KEY_SCHEMA)
        current = int(row.valor) if row and row.valor.isdigit() else 0
        if current < SCHEMA_VERSION and row is not None:
            row.valor = str(SCHEMA_VERSION)


def integrity_report() -> tuple[bool, list[str]]:
    """Verificação administrativa do banco, sem qualquer reparo automático.

    Devolve (tudo_ok, mensagens). Reparo destrutivo nunca é tentado: se algo
    estiver errado, o administrador é avisado para restaurar um backup.
    """
    engine = get_engine()
    problemas: list[str] = []
    if engine.dialect.name != "sqlite":
        return True, ["Verificação de arquivo disponível apenas no modo local (SQLite)."]

    with engine.connect() as connection:
        integridade = connection.execute(sa.text("PRAGMA integrity_check")).scalars().all()
        if [str(r).lower() for r in integridade] != ["ok"]:
            problemas.extend(f"Integridade: {linha}" for linha in integridade)

        orfaos = connection.execute(sa.text("PRAGMA foreign_key_check")).all()
        for linha in orfaos:
            problemas.append(f"Vínculo quebrado na tabela {linha[0]} (registro {linha[1]}).")

    return not problemas, problemas or ["Nenhum problema encontrado no banco de dados."]


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
