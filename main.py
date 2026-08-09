"""Ponto de entrada do SYS CREDIÁRIO (aplicativo desktop para Windows)."""

from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path
from types import TracebackType

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from app.config import APP_NAME, APP_VERSION, settings  # noqa: E402
from app.database.migrations import run_migrations  # noqa: E402
from app.security.authentication import current_session  # noqa: E402

logger = logging.getLogger("sys_crediario")


def configure_logging() -> None:
    settings.ensure_dirs()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(settings.log_dir / "sys_crediario.log", encoding="utf-8")
        ],
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


def main() -> int:
    configure_logging()
    logger.info("Iniciando %s %s", APP_NAME, APP_VERSION)

    try:
        run_migrations()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Falha ao preparar o banco de dados")
        print(f"Erro ao preparar o banco de dados: {exc}", file=sys.stderr)
        return 1

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
