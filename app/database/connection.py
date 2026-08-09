"""Engine, sessões e ciclo de vida da conexão."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_database_url: str = settings.database_url


@sa.event.listens_for(Engine, "connect")
def _configure_sqlite(dbapi_connection, connection_record) -> None:  # noqa: ANN001
    """Chaves estrangeiras e journal WAL para robustez no SQLite."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


def configure(database_url: str) -> None:
    """Aponta a aplicação para outro banco (testes ou PostgreSQL)."""
    global _database_url
    dispose_engine()
    _database_url = database_url


def current_url() -> str:
    return _database_url


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        kwargs: dict[str, object] = {"future": True, "pool_pre_ping": True}
        if _database_url.startswith("sqlite"):
            settings.ensure_dirs()
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
        _engine = sa.create_engine(_database_url, **kwargs)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), expire_on_commit=False, future=True
        )
    return _session_factory


def new_session() -> Session:
    return get_session_factory()()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Sessão transacional: commit no sucesso, rollback em qualquer erro."""
    session = new_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def dispose_engine() -> None:
    """Fecha todas as conexões — obrigatório antes de restaurar um backup."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
