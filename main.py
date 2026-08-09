"""Ponto de entrada do SYS CREDIÁRIO (aplicativo desktop para Windows)."""

from __future__ import annotations

import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

#: A verificação da instalação precisa de um banco descartável. Isso é decidido
#: aqui, antes de `app.config` ser importado, porque os caminhos são resolvidos
#: no momento do import — do contrário a verificação escreveria (e deixaria um
#: usuário) no banco real da loja.
SELF_CHECK = "--verificar" in sys.argv
if SELF_CHECK:
    import tempfile

    # A pasta real da loja é guardada antes da troca, para o relatório da
    # verificação ser gravado onde quem instalou consegue achar. O nome precisa
    # acompanhar APP_SLUG em app/config.py (há teste garantindo isso).
    _REAL_HOME = os.environ.get("SYS_HOME") or str(Path.home() / "SYS_Crediario")
    os.environ["SYS_VERIFICACAO_DESTINO"] = _REAL_HOME

    _SANDBOX = tempfile.mkdtemp(prefix="sys_verificacao_")
    os.environ["SYS_HOME"] = _SANDBOX

from app.config import APP_NAME, APP_VERSION, settings  # noqa: E402
from app.database.migrations import run_migrations  # noqa: E402
from app.security.authentication import current_session  # noqa: E402

logger = logging.getLogger("sys_crediario")


def configure_logging() -> None:
    """Log técnico rotativo: nunca cresce sem limite no computador da empresa."""
    settings.ensure_dirs()
    handler = RotatingFileHandler(
        settings.log_dir / "sys_crediario.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[handler],
    )


def install_exception_hook() -> None:
    """Nenhum erro inesperado derruba o programa em silêncio."""
    from PySide6.QtWidgets import QMessageBox

    def hook(
        kind: type[BaseException], value: BaseException, tb: TracebackType | None
    ) -> None:
        logger.error("Erro inesperado", exc_info=(kind, value, tb))
        traceback.print_exception(kind, value, tb)
        QMessageBox.critical(
            None,
            f"{APP_NAME} — erro inesperado",
            f"{value}\n\nO detalhe técnico foi gravado em:\n{settings.log_dir}",
        )

    sys.excepthook = hook


def _self_check() -> int:
    """Modo `--verificar`: confere a instalação em um banco descartável.

    Nada é escrito na pasta de dados da loja e nenhum usuário fica para trás.
    """
    import shutil

    configure_logging()
    from app.selfcheck import report

    try:
        return report()
    finally:
        shutil.rmtree(_SANDBOX, ignore_errors=True)


def main() -> int:
    if "--versao" in sys.argv or "-v" in sys.argv:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0
    if SELF_CHECK:
        return _self_check()

    configure_logging()
    logger.info("Iniciando %s %s", APP_NAME, APP_VERSION)

    try:
        run_migrations()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Falha ao preparar o banco de dados")
        print(f"Erro ao preparar o banco de dados: {exc}", file=sys.stderr)
        return 1

    # Backup automático na abertura. Falha aqui não impede o uso do sistema:
    # o serviço já trata destino indisponível e apenas registra no log.
    try:
        from app.services.backup_service import auto_backup_if_due

        if auto_backup_if_due() is not None:
            logger.info("Backup automático concluído na inicialização.")
    except Exception:  # noqa: BLE001 - backup nunca derruba o programa
        logger.exception("Backup automático falhou na inicialização")

    from PySide6.QtWidgets import QApplication, QDialog

    from app.ui import icons
    from app.ui.login_window import LoginWindow
    from app.ui.main_window import MainWindow
    from app.ui.theme import ACCENT, STYLESHEET

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("SYS")
    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(icons.icon("shield", ACCENT, 64))
    install_exception_hook()

    while True:
        login = LoginWindow()
        if login.exec() != QDialog.DialogCode.Accepted or login.session_user is None:
            return 0

        current_session.login(login.session_user)
        window = MainWindow(login.session_user)
        window.show()
        app.exec()

        if not window.logged_out:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
