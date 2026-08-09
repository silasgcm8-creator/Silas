"""Tela de login e criação do administrador no primeiro uso."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_NAME, APP_VERSION
from app.security.authentication import AuthenticationError, SessionUser
from app.services import user_service
from app.services.errors import BusinessError, ValidationError
from app.ui import icons
from app.ui.theme import ACCENT, TEXT_MUTED
from app.ui.widgets import Card, button, field_label, primary_button, warn


class LoginWindow(QDialog):
    """Porta de entrada do sistema."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session_user: SessionUser | None = None
        self.first_run = not user_service.has_admin()

        self.setWindowTitle(APP_NAME)
        self.setFixedSize(430, 560 if self.first_run else 460)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(16)

        brand = QLabel()
        brand.setPixmap(icons.pixmap("shield", ACCENT, 44))
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(brand)

        title = QLabel(APP_NAME)
        title.setObjectName("Brand")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel(
            "Crie o usuário do proprietário para começar"
            if self.first_run
            else "Entre com seu usuário e senha"
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        card = Card()
        form = QFormLayout()
        form.setSpacing(10)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nome do proprietário")
        self.user_edit = QLineEdit()
        self.user_edit.setPlaceholderText("usuario")
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_edit.setPlaceholderText("••••••")
        self.confirm_edit = QLineEdit()
        self.confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_edit.setPlaceholderText("Repita a senha")

        if self.first_run:
            form.addRow(field_label("NOME COMPLETO"), self.name_edit)
        form.addRow(field_label("USUÁRIO"), self.user_edit)
        form.addRow(field_label("SENHA"), self.pass_edit)
        if self.first_run:
            form.addRow(field_label("CONFIRMAR SENHA"), self.confirm_edit)
        card.body.addLayout(form)
        layout.addWidget(card)

        self.enter_button = primary_button(
            "Criar administrador e entrar" if self.first_run else "Entrar", "logout"
        )
        self.enter_button.clicked.connect(self._submit)
        layout.addWidget(self.enter_button)

        footer = QHBoxLayout()
        cancel = button("Sair", ghost=True)
        cancel.clicked.connect(self.reject)
        version = QLabel(f"versão {APP_VERSION}")
        version.setObjectName("Muted")
        version.setStyleSheet(f"color: {TEXT_MUTED};")
        footer.addWidget(version)
        footer.addStretch(1)
        footer.addWidget(cancel)
        layout.addLayout(footer)

        for widget in (self.user_edit, self.pass_edit, self.confirm_edit, self.name_edit):
            widget.returnPressed.connect(self._submit)

        (self.name_edit if self.first_run else self.user_edit).setFocus()

    def _submit(self) -> None:
        if self.first_run:
            self._create_admin()
        else:
            self._login()

    def _create_admin(self) -> None:
        if self.pass_edit.text() != self.confirm_edit.text():
            warn(self, "Senha", "As senhas digitadas não conferem.")
            return
        try:
            self.session_user = user_service.create_first_admin(
                self.name_edit.text(), self.user_edit.text(), self.pass_edit.text()
            )
        except (ValidationError, BusinessError) as exc:
            warn(self, "Não foi possível criar", str(exc))
            return
        self.accept()

    def _login(self) -> None:
        try:
            self.session_user = user_service.authenticate(
                self.user_edit.text(), self.pass_edit.text()
            )
        except AuthenticationError as exc:
            warn(self, "Entrada negada", str(exc))
            self.pass_edit.clear()
            self.pass_edit.setFocus()
            return
        self.accept()
