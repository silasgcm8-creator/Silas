"""Configuração dos testes: banco temporário e usuário administrador."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

# Precisa ser definido ANTES de qualquer importação de app.config.
_TEMP_HOME = Path(tempfile.mkdtemp(prefix="sys_crediario_testes_"))
os.environ["SYS_HOME"] = str(_TEMP_HOME)

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    """Cada teste começa com um banco vazio e recém-criado."""
    from app.config import settings
    from app.database import connection
    from app.database.migrations import run_migrations
    from app.security.authentication import login_throttle, token_store

    # Estado em memória também precisa começar limpo, senão o bloqueio por
    # tentativas e os tokens da API vazam de um teste para o outro.
    login_throttle.reset()
    token_store.clear()

    connection.dispose_engine()
    settings.ensure_dirs()
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(settings.db_file) + suffix)
        if candidate.exists():
            candidate.unlink()
    run_migrations()

    yield

    connection.dispose_engine()


@pytest.fixture()
def admin():
    from app.services import user_service

    return user_service.create_first_admin("Proprietário SYS", "admin", "senha123")


@pytest.fixture()
def cliente(admin):
    from app.services import client_service

    return client_service.create_client(
        "Maria Aparecida Souza", "529.982.247-25", "(62) 99888-7766", admin
    )


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ANN001, ARG001
    shutil.rmtree(_TEMP_HOME, ignore_errors=True)
