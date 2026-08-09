"""Backup e restauração do banco local."""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa

from app.config import APP_SLUG, DB_SIGNATURE, settings
from app.database.connection import current_url, dispose_engine, session_scope
from app.database.migrations import read_signature
from app.models.log import LogAction
from app.security.authentication import SessionUser
from app.security.permissions import Permission, require
from app.services import log_service
from app.services.errors import BusinessError
from app.utils.dates import timestamp_tag

SQLITE_HEADER = b"SQLite format 3\x00"


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    created_at: datetime
    size_bytes: int

    @property
    def size_mb(self) -> float:
        return round(self.size_bytes / (1024 * 1024), 2)


def default_backup_name(moment: datetime | None = None) -> str:
    return f"{APP_SLUG}_Backup_{timestamp_tag(moment)}.db"


def _require_sqlite() -> Path:
    if not current_url().startswith("sqlite"):
        raise BusinessError(
            "Backup por arquivo disponível apenas no modo local (SQLite). "
            "Em servidor PostgreSQL utilize a rotina de backup do servidor."
        )
    return settings.db_file


def _copy_database(source: Path, target: Path) -> Path:
    """Cópia consistente via API de backup do SQLite (inclui o conteúdo do WAL)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    origin = sqlite3.connect(str(source))
    try:
        copy = sqlite3.connect(str(target))
        try:
            origin.backup(copy)
        finally:
            copy.close()
    finally:
        origin.close()
    return target


def create_backup(destination: Path | str | None = None, actor: SessionUser | None = None) -> Path:
    """Copia o banco de forma consistente, usando a API de backup do SQLite."""
    if actor:
        require(actor.role, Permission.BACKUP_CREATE)
    source = _require_sqlite()
    if not source.exists():
        raise BusinessError("Banco de dados ainda não foi criado.")

    settings.ensure_dirs()
    target = Path(destination) if destination else settings.backup_dir / default_backup_name()
    _copy_database(source, target)

    with session_scope() as session:
        log_service.record(
            session, LogAction.BACKUP_CREATED, actor, detalhes=str(target)
        )
    return target


def looks_like_sys_backup(path: Path | str) -> bool:
    """Confere cabeçalho SQLite, tabelas obrigatórias e assinatura do sistema."""
    file = Path(path)
    if not file.is_file() or file.stat().st_size < 512:
        return False
    with file.open("rb") as handle:
        if handle.read(16) != SQLITE_HEADER:
            return False

    engine = sa.create_engine(f"sqlite:///{file}")
    try:
        tables = set(sa.inspect(engine).get_table_names())
        required = {"clientes", "crediarios", "parcelas", "usuarios", "configuracoes"}
        if not required.issubset(tables):
            return False
        return read_signature(engine) == DB_SIGNATURE
    except sa.exc.SQLAlchemyError:
        return False
    finally:
        engine.dispose()


def restore_backup(source: Path | str, actor: SessionUser | None = None) -> Path:
    """Valida, guarda o banco atual e só então substitui os dados."""
    if actor:
        require(actor.role, Permission.BACKUP_RESTORE)
    origin = Path(source)
    if not looks_like_sys_backup(origin):
        raise BusinessError(
            "O arquivo selecionado não é um backup válido do SYS CREDIÁRIO."
        )

    target = _require_sqlite()
    settings.ensure_dirs()
    safety = settings.backup_dir / f"{APP_SLUG}_AntesDaRestauracao_{timestamp_tag()}.db"

    dispose_engine()
    if target.exists():
        _copy_database(target, safety)
    for suffix in ("-wal", "-shm"):
        extra = Path(str(target) + suffix)
        if extra.exists():
            extra.unlink()
    shutil.copy2(origin, target)

    with session_scope() as session:
        log_service.record(
            session,
            LogAction.BACKUP_RESTORED,
            actor,
            detalhes=f"{origin} (cópia de segurança: {safety.name})",
        )
    return safety


def list_backups() -> list[BackupInfo]:
    settings.ensure_dirs()
    files = sorted(
        settings.backup_dir.glob("*.db"), key=lambda f: f.stat().st_mtime, reverse=True
    )
    return [
        BackupInfo(
            path=file,
            created_at=datetime.fromtimestamp(file.stat().st_mtime),
            size_bytes=file.stat().st_size,
        )
        for file in files
    ]
