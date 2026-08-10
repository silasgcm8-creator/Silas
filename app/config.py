"""Configuração central do SYS CREDIÁRIO.

Todos os caminhos de dados ficam em uma pasta persistente do usuário para que
uma atualização do programa (ou a substituição do .exe) nunca apague dados.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "SYS CREDIÁRIO"
#: Nome da empresa impresso nos comprovantes e carnês. É só o padrão inicial:
#: o administrador altera em Configurações → Empresa e Pix.
COMPANY_DEFAULT = "Ótica Visão"
APP_SLUG = "SYS_Crediario"
APP_VERSION = "1.1.0"
APP_ORG = "SYS"

#: Marca gravada na tabela de configurações; usada para validar backups.
DB_SIGNATURE = "SYS_CREDIARIO"
#: 2 — índice único de recebimento por parcela (impede pagamento em duplicidade).
#: 3 — estorno auditado: código da operação, exclusão lógica do recebimento e
#:     índice único parcial, para a parcela poder ser paga de novo após estorno.
#: 4 — exclusão lógica de cliente (excluido_em / por / motivo).
#: 5 — módulo de cobranças: contas de recebimento, documentos e histórico.
#: 6 — observação operacional do recebimento (pagamentos.observacao).
SCHEMA_VERSION = 6


def base_dir() -> Path:
    """Pasta raiz persistente dos dados (ex.: C:/Users/USUARIO/SYS_Crediario)."""
    override = os.environ.get("SYS_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / APP_SLUG


def resource_path(relative: str) -> Path:
    """Resolve um recurso interno tanto em modo script quanto empacotado."""
    bundle = getattr(sys, "_MEIPASS", None)
    root = Path(bundle) if bundle else Path(__file__).resolve().parent.parent
    return root / relative


@dataclass(frozen=True)
class Settings:
    """Configuração efetiva da execução atual."""

    base_dir: Path
    data_dir: Path
    backup_dir: Path
    log_dir: Path
    receipt_dir: Path
    db_file: Path
    database_url: str
    api_host: str
    api_port: int
    session_timeout_minutes: int
    login_max_attempts: int
    login_lock_minutes: int

    def ensure_dirs(self) -> None:
        for folder in (
            self.base_dir,
            self.data_dir,
            self.backup_dir,
            self.log_dir,
            self.receipt_dir,
        ):
            folder.mkdir(parents=True, exist_ok=True)


def _database_url(db_file: Path) -> str:
    """URL do banco.

    Por padrão SQLite local. Definindo SYS_DATABASE_URL o mesmo código passa a
    operar com PostgreSQL (ex.: postgresql+psycopg://user:senha@host/sys).
    """
    external = os.environ.get("SYS_DATABASE_URL")
    if external:
        return external
    return f"sqlite:///{db_file}"


def get_settings() -> Settings:
    root = base_dir()
    data_dir = root / "data"
    db_file = data_dir / "sys_crediario.db"
    settings = Settings(
        base_dir=root,
        data_dir=data_dir,
        backup_dir=root / "backups",
        log_dir=root / "logs",
        receipt_dir=root / "comprovantes",
        db_file=db_file,
        database_url=_database_url(db_file),
        api_host=os.environ.get("SYS_API_HOST", "0.0.0.0"),
        api_port=int(os.environ.get("SYS_API_PORT", "8765")),
        session_timeout_minutes=int(os.environ.get("SYS_SESSION_TIMEOUT", "720")),
        login_max_attempts=int(os.environ.get("SYS_LOGIN_MAX_ATTEMPTS", "5")),
        login_lock_minutes=int(os.environ.get("SYS_LOGIN_LOCK_MINUTES", "10")),
    )
    return settings


settings = get_settings()
