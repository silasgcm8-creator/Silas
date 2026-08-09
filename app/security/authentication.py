"""Autenticação, sessão da área de trabalho e tokens da API."""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.config import settings
from app.models.status import Role
from app.security.permissions import Permission, can


class AuthenticationError(Exception):
    """Usuário ou senha incorretos, ou usuário desativado."""


@dataclass(frozen=True)
class SessionUser:
    """Identidade autenticada, sem carregar o objeto ORM entre threads."""

    id: int
    usuario: str
    nome: str
    role: Role

    @property
    def is_admin(self) -> bool:
        return self.role is Role.ADMIN

    def can(self, permission: Permission) -> bool:
        return can(self.role, permission)


@dataclass
class CurrentSession:
    """Sessão única do aplicativo desktop."""

    user: SessionUser | None = None
    started_at: datetime | None = None

    def login(self, user: SessionUser) -> None:
        self.user = user
        self.started_at = datetime.now()

    def logout(self) -> None:
        self.user = None
        self.started_at = None

    @property
    def is_authenticated(self) -> bool:
        if self.user is None or self.started_at is None:
            return False
        limit = timedelta(minutes=settings.session_timeout_minutes)
        return datetime.now() - self.started_at <= limit

    def require_user(self) -> SessionUser:
        if not self.is_authenticated or self.user is None:
            raise AuthenticationError("Sessão expirada. Entre novamente.")
        return self.user


current_session = CurrentSession()


@dataclass
class _Attempts:
    failures: int = 0
    locked_until: datetime | None = None


@dataclass
class LoginThrottle:
    """Bloqueio temporário após seguidas senhas erradas.

    A API local fica exposta no Wi‑Fi da empresa, então sem esse limite alguém
    na mesma rede poderia testar senhas indefinidamente. O bloqueio é por
    usuário, temporário e se desfaz sozinho — nenhum funcionário fica trancado
    fora do sistema de forma permanente.
    """

    max_attempts: int = 5
    lock_minutes: int = 10
    _attempts: dict[str, _Attempts] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def locked_for(self, key: str) -> int:
        """Minutos que ainda faltam para liberar; 0 quando está liberado."""
        with self._lock:
            entry = self._attempts.get(key)
            if entry is None or entry.locked_until is None:
                return 0
            remaining = entry.locked_until - datetime.now()
            if remaining.total_seconds() <= 0:
                self._attempts.pop(key, None)
                return 0
            return max(1, int(remaining.total_seconds() // 60) + 1)

    def ensure_allowed(self, key: str) -> None:
        minutes = self.locked_for(key)
        if minutes:
            raise AuthenticationError(
                "Muitas tentativas de senha incorreta. "
                f"Tente novamente em {minutes} minuto(s)."
            )

    def register_failure(self, key: str) -> None:
        with self._lock:
            entry = self._attempts.setdefault(key, _Attempts())
            entry.failures += 1
            if entry.failures >= self.max_attempts:
                entry.locked_until = datetime.now() + timedelta(minutes=self.lock_minutes)

    def register_success(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._attempts.clear()


@dataclass
class _Token:
    user: SessionUser
    expires_at: datetime


@dataclass
class TokenStore:
    """Tokens em memória usados pela API local (nunca gravados em disco)."""

    ttl_minutes: int = 720
    _tokens: dict[str, _Token] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def issue(self, user: SessionUser) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._tokens[token] = _Token(
                user=user, expires_at=datetime.now() + timedelta(minutes=self.ttl_minutes)
            )
        return token

    def resolve(self, token: str) -> SessionUser | None:
        with self._lock:
            entry = self._tokens.get(token or "")
            if entry is None:
                return None
            if entry.expires_at < datetime.now():
                self._tokens.pop(token, None)
                return None
            return entry.user

    def revoke(self, token: str) -> None:
        with self._lock:
            self._tokens.pop(token, None)

    def clear(self) -> None:
        with self._lock:
            self._tokens.clear()


token_store = TokenStore(ttl_minutes=settings.session_timeout_minutes)
login_throttle = LoginThrottle(
    max_attempts=settings.login_max_attempts, lock_minutes=settings.login_lock_minutes
)
