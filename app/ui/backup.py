"""Backup e restauração pela interface."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.config import settings
from app.database.connection import current_url
from app.security.permissions import Permission, PermissionDenied
from app.services import backup_service
from app.services.errors import BusinessError
from app.ui.context import AppContext
from app.ui.theme import GREEN, YELLOW
from app.ui.widgets import (
    Card,
    DataTable,
    SectionTitle,
    button,
    confirm,
    danger_button,
    error,
    field_label,
    info,
    page_header,
    primary_button,
    text_item,
    warn,
)
from app.utils.dates import format_datetime_br


class BackupPage(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(
            page_header("Backup", "Proteja os dados do crediário em poucos cliques")
        )

        card = Card()
        card.body.addWidget(field_label("BANCO DE DADOS EM USO"))
        self.path_label = QLabel(str(settings.db_file))
        self.path_label.setObjectName("CardValue")
        self.path_label.setWordWrap(True)
        card.body.addWidget(self.path_label)

        self.mode_label = QLabel("")
        self.mode_label.setObjectName("Muted")
        card.body.addWidget(self.mode_label)

        actions = QHBoxLayout()
        create = primary_button("Criar backup", "download")
        create.clicked.connect(self._create)
        create.setEnabled(ctx.can(Permission.BACKUP_CREATE))
        restore = danger_button("Restaurar backup", "upload")
        restore.clicked.connect(self._restore)
        restore.setEnabled(ctx.can(Permission.BACKUP_RESTORE))
        if not ctx.can(Permission.BACKUP_RESTORE):
            restore.setToolTip("Somente o administrador pode restaurar um backup.")
        folder = button("Abrir pasta de backups", "list")
        folder.clicked.connect(self._open_folder)
        check = button("Verificar banco de dados", "check")
        check.clicked.connect(self._check)
        check.setEnabled(ctx.can(Permission.DB_CHECK))
        if not ctx.can(Permission.DB_CHECK):
            check.setToolTip("Somente o administrador pode verificar o banco.")
        actions.addWidget(create)
        actions.addWidget(restore)
        actions.addWidget(folder)
        actions.addWidget(check)
        actions.addStretch(1)
        card.body.addLayout(actions)
        layout.addWidget(card)

        layout.addWidget(SectionTitle("Backups na pasta padrão"))
        self.table = DataTable(["Arquivo", "Criado em", "Tamanho"], stretch=0, sortable=False)
        layout.addWidget(self.table, 1)

        self.hint = QLabel(
            "O backup é um arquivo .db. Guarde uma cópia em pen drive ou nuvem. "
            "Antes de restaurar, o sistema salva automaticamente uma cópia dos dados atuais."
        )
        self.hint.setObjectName("Muted")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

    def refresh(self) -> None:
        local = current_url().startswith("sqlite")
        self.mode_label.setText(
            "Modo local (SQLite) — funciona totalmente offline."
            if local
            else "Modo servidor: use a rotina de backup do PostgreSQL."
        )
        self.mode_label.setStyleSheet(f"color: {GREEN if local else YELLOW};")
        self.path_label.setText(str(settings.db_file) if local else current_url())

        self.table.fill(
            [
                [
                    text_item(item.path.name),
                    text_item(format_datetime_br(item.created_at)),
                    text_item(f"{item.size_mb} MB"),
                ]
                for item in backup_service.list_backups()
            ]
        )

    def _create(self) -> None:
        suggestion = settings.backup_dir / backup_service.default_backup_name()
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar backup", str(suggestion), "Banco SYS (*.db)"
        )
        if not path:
            return
        try:
            saved = backup_service.create_backup(Path(path), self.ctx.user)
        except (BusinessError, PermissionDenied) as exc:
            error(self, "Backup", str(exc))
            return
        self.refresh()
        info(self, "Backup criado", f"Arquivo salvo em:\n{saved}")

    def _restore(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar backup", str(settings.backup_dir), "Banco SYS (*.db);;Todos (*.*)"
        )
        if not path:
            return
        if not backup_service.looks_like_sys_backup(path):
            error(
                self,
                "Arquivo inválido",
                "O arquivo selecionado não é um backup do SYS CREDIÁRIO.",
            )
            return
        if not confirm(
            self,
            "Restaurar backup",
            "Os dados atuais serão substituídos pelos dados do backup.\n"
            "Uma cópia de segurança será criada automaticamente antes.\n\nContinuar?",
        ):
            return
        try:
            safety = backup_service.restore_backup(path, self.ctx.user)
        except (BusinessError, PermissionDenied) as exc:
            error(self, "Restauração", str(exc))
            return
        self.ctx.notify("Backup restaurado.")
        self.refresh()
        info(
            self,
            "Backup restaurado",
            f"Dados restaurados com sucesso.\nCópia dos dados anteriores: {safety.name}",
        )

    def _check(self) -> None:
        """Diagnostica o banco. Nenhum reparo automático é tentado."""
        try:
            ok, mensagens = backup_service.check_database(self.ctx.user)
        except (BusinessError, PermissionDenied) as exc:
            warn(self, "Verificação", str(exc))
            return

        texto = "\n".join(f"• {m}" for m in mensagens)
        if ok:
            info(self, "Banco de dados verificado", texto)
            self.ctx.notify("Banco de dados verificado: nenhum problema.")
            return
        error(
            self,
            "Problema no banco de dados",
            f"{texto}\n\nNão foi tentado nenhum reparo automático, para não "
            "arriscar os dados. Crie um backup do estado atual e restaure o "
            "último backup bom.",
        )

    def _open_folder(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        settings.ensure_dirs()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(settings.backup_dir)))
