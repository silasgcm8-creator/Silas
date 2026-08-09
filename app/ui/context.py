"""Estado compartilhado entre as telas."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from app.security.authentication import SessionUser
from app.security.permissions import Permission


class AppContext(QObject):
    """Usuário autenticado + aviso global de que os dados mudaram."""

    data_changed = Signal()
    status_message = Signal(str)

    def __init__(self, user: SessionUser) -> None:
        super().__init__()
        self._user = user

    @property
    def user(self) -> SessionUser:
        return self._user

    def can(self, permission: Permission) -> bool:
        return self._user.can(permission)

    def notify(self, message: str = "") -> None:
        if message:
            self.status_message.emit(message)
        self.data_changed.emit()
