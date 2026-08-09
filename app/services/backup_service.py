"""Backup e restauração do banco local."""

from __future__ import annotations

import logging
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import sqlalchemy as sa

from app.config import APP_SLUG, DB_SIGNATURE, settings
from app.database.connection import current_url, dispose_engine, session_scope
from app.database.migrations import integrity_report, read_signature, run_migrations
from app.models.log import LogAction
from app.models.setting import Setting
from app.security.authentication import SessionUser
from app.security.permissions import Permission, require
from app.services import log_service
from app.services.errors import BusinessError
from app.utils.dates import timestamp_tag, timestamp_tag_seconds

LOGGER = logging.getLogger("sys_crediario")

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

    # Um backup pode ter sido gerado por uma versão anterior do programa, então
    # o banco restaurado passa pelas migrações antes de voltar a ser usado.
    run_migrations()

    with session_scope() as session:
        log_service.record(
            session,
            LogAction.BACKUP_RESTORED,
            actor,
            detalhes=f"{origin} (cópia de segurança: {safety.name})",
        )
    return safety


KEY_AUTO_ENABLED = "backup.automatico"
KEY_AUTO_HOURS = "backup.intervalo_horas"
KEY_AUTO_FOLDER = "backup.pasta"
KEY_AUTO_KEEP = "backup.manter"
KEY_AUTO_LAST = "backup.ultimo_automatico"

#: Padrões conservadores: ligado, uma vez por dia, guardando as 15 últimas
#: cópias na pasta do sistema. Perder backup é pior que gastar disco.
AUTO_DEFAULTS = {
    KEY_AUTO_ENABLED: "1",
    KEY_AUTO_HOURS: "24",
    KEY_AUTO_FOLDER: "",
    KEY_AUTO_KEEP: "15",
}


@dataclass(frozen=True)
class AutoBackupConfig:
    enabled: bool
    interval_hours: int
    folder: Path
    keep: int
    last_run: datetime | None

    @property
    def due(self) -> bool:
        if not self.enabled:
            return False
        if self.last_run is None:
            return True
        return datetime.now() - self.last_run >= timedelta(hours=self.interval_hours)


def _read_setting(session, key: str, default: str = "") -> str:  # noqa: ANN001
    row = session.get(Setting, key)
    return (row.valor if row else "") or default


def auto_config() -> AutoBackupConfig:
    """Configuração do backup automático, com padrões seguros."""
    with session_scope() as session:
        enabled = _read_setting(session, KEY_AUTO_ENABLED, AUTO_DEFAULTS[KEY_AUTO_ENABLED])
        horas = _read_setting(session, KEY_AUTO_HOURS, AUTO_DEFAULTS[KEY_AUTO_HOURS])
        pasta = _read_setting(session, KEY_AUTO_FOLDER)
        manter = _read_setting(session, KEY_AUTO_KEEP, AUTO_DEFAULTS[KEY_AUTO_KEEP])
        ultimo = _read_setting(session, KEY_AUTO_LAST)

    try:
        quando = datetime.fromisoformat(ultimo) if ultimo else None
    except ValueError:  # valor corrompido não pode travar o backup
        quando = None

    return AutoBackupConfig(
        enabled=enabled == "1",
        interval_hours=max(1, int(horas) if horas.isdigit() else 24),
        folder=Path(pasta).expanduser() if pasta else settings.backup_dir,
        keep=max(1, int(manter) if manter.isdigit() else 15),
        last_run=quando,
    )


def save_auto_config(
    enabled: bool,
    interval_hours: int,
    folder: Path | str | None,
    keep: int,
    actor: SessionUser | None = None,
) -> AutoBackupConfig:
    """Grava a configuração do backup automático (só administrador)."""
    if actor:
        require(actor.role, Permission.SETTINGS)
    if interval_hours < 1:
        raise BusinessError("O intervalo do backup automático deve ser de 1 hora ou mais.")
    if keep < 1:
        raise BusinessError("É preciso manter pelo menos 1 backup automático.")

    destino = Path(folder).expanduser() if folder else None
    if destino is not None:
        try:
            destino.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise BusinessError(
                f"Não foi possível usar a pasta escolhida para backup: {exc}"
            ) from exc

    with session_scope() as session:
        for chave, valor in (
            (KEY_AUTO_ENABLED, "1" if enabled else "0"),
            (KEY_AUTO_HOURS, str(interval_hours)),
            (KEY_AUTO_FOLDER, str(destino) if destino else ""),
            (KEY_AUTO_KEEP, str(keep)),
        ):
            row = session.get(Setting, chave)
            if row is None:
                session.add(Setting(chave=chave, valor=valor))
            else:
                row.valor = valor
    return auto_config()


def _prune_auto_backups(folder: Path, keep: int) -> int:
    """Apaga as cópias automáticas mais antigas além do limite configurado.

    Só toca em arquivos com o prefixo automático: backups manuais e as cópias
    de segurança feitas antes de uma restauração nunca são removidos.
    """
    arquivos = sorted(
        folder.glob(f"{APP_SLUG}_Auto_*.db"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    removidos = 0
    for antigo in arquivos[keep:]:
        try:
            antigo.unlink()
            removidos += 1
        except OSError:  # arquivo em uso ou sem permissão: não é motivo de falha
            continue
    return removidos


def auto_backup_if_due(force: bool = False) -> Path | None:
    """Cria o backup automático se já passou do intervalo configurado.

    Chamada na abertura do programa. Nunca derruba o sistema: se o destino
    estiver indisponível (pen drive removido, rede fora), registra no log e
    segue. Devolve o caminho gerado, ou None quando não havia o que fazer.
    """
    config = auto_config()
    if not force and not config.due:
        return None

    source = _require_sqlite()
    if not source.exists():
        return None

    destino = config.folder / f"{APP_SLUG}_Auto_{timestamp_tag_seconds()}.db"
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        _copy_database(source, destino)
    except (OSError, sqlite3.Error) as exc:
        LOGGER.warning("Backup automático não pôde ser gravado em %s: %s", destino, exc)
        return None

    removidos = _prune_auto_backups(config.folder, config.keep)

    with session_scope() as session:
        row = session.get(Setting, KEY_AUTO_LAST)
        agora = datetime.now().isoformat(timespec="seconds")
        if row is None:
            session.add(Setting(chave=KEY_AUTO_LAST, valor=agora))
        else:
            row.valor = agora
        detalhe = f"automático: {destino}"
        if removidos:
            detalhe += f" ({removidos} cópia(s) antiga(s) removida(s))"
        log_service.record(session, LogAction.BACKUP_CREATED, None, detalhes=detalhe)

    LOGGER.info("Backup automático gravado em %s", destino)
    return destino


def check_database(actor: SessionUser | None = None) -> tuple[bool, list[str]]:
    """Verificação do banco pedida pelo administrador.

    Só diagnostica: nenhum reparo automático é tentado, porque um reparo
    malfeito destrói dados. Se houver problema, o caminho seguro é restaurar
    um backup.
    """
    if actor:
        require(actor.role, Permission.DB_CHECK)
    ok, mensagens = integrity_report()

    with session_scope() as session:
        log_service.record(
            session,
            LogAction.INTEGRITY_CHECK,
            actor,
            detalhes="sem problemas" if ok else "; ".join(mensagens)[:380],
        )
    return ok, mensagens


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
