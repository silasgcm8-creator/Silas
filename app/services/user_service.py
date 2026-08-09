"""Usuários, primeiro acesso e autenticação."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.database.connection import session_scope
from app.models.log import LogAction
from app.models.status import Role
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.security.authentication import AuthenticationError, SessionUser
from app.security.password import hash_password, needs_rehash, verify_password
from app.security.permissions import Permission, require
from app.services import log_service
from app.services.errors import BusinessError, NotFoundError
from app.utils.validators import (
    ValidationError,
    validate_name,
    validate_password,
    validate_username,
)


@dataclass(frozen=True)
class UserRow:
    id: int
    usuario: str
    nome: str
    papel: str
    ativo: bool
    ultimo_acesso: datetime | None


def has_admin() -> bool:
    with session_scope() as session:
        return UserRepository(session).has_admin()


def create_first_admin(nome: str, usuario: str, senha: str) -> SessionUser:
    """Criação do proprietário no primeiro uso do sistema."""
    with session_scope() as session:
        repo = UserRepository(session)
        if repo.has_admin():
            raise BusinessError("Já existe um administrador cadastrado.")
        user = _build_user(repo, nome, usuario, senha, Role.ADMIN)
        session.flush()
        log_service.record(
            session, LogAction.USER_CREATED, None, detalhes=f"admin inicial: {user.usuario}"
        )
        return _to_session_user(user)


def create_user(
    nome: str, usuario: str, senha: str, papel: Role, actor: SessionUser
) -> int:
    require(actor.role, Permission.USER_MANAGE)
    with session_scope() as session:
        repo = UserRepository(session)
        user = _build_user(repo, nome, usuario, senha, papel)
        session.flush()
        log_service.record(
            session,
            LogAction.USER_CREATED,
            actor,
            detalhes=f"{user.usuario} ({papel.label})",
        )
        return user.id


def _build_user(
    repo: UserRepository, nome: str, usuario: str, senha: str, papel: Role
) -> User:
    nome = validate_name(nome)
    usuario = validate_username(usuario)
    senha = validate_password(senha)
    if repo.get_by_username(usuario) is not None:
        raise BusinessError("Este nome de usuário já existe.")
    return repo.add(
        User(
            usuario=usuario,
            nome=nome,
            senha_hash=hash_password(senha),
            papel=papel.value,
            ativo=True,
        )
    )


def authenticate(usuario: str, senha: str) -> SessionUser:
    username = (usuario or "").strip().lower()
    with session_scope() as session:
        repo = UserRepository(session)
        user = repo.get_by_username(username)
        if user is None or not verify_password(senha, user.senha_hash):
            log_service.record(
                session, LogAction.LOGIN_FAILED, None, detalhes=f"usuário: {username}"
            )
            raise AuthenticationError("Usuário ou senha incorretos.")
        if not user.ativo:
            raise AuthenticationError("Usuário desativado. Procure o administrador.")

        if needs_rehash(user.senha_hash):
            user.senha_hash = hash_password(senha)
        user.ultimo_acesso = datetime.now()
        identity = _to_session_user(user)
        log_service.record(session, LogAction.LOGIN, identity)
        return identity


def change_password(user_id: int, nova_senha: str, actor: SessionUser) -> None:
    if actor.id != user_id:
        require(actor.role, Permission.USER_MANAGE)
    nova_senha = validate_password(nova_senha)
    with session_scope() as session:
        user = UserRepository(session).get(user_id)
        if user is None:
            raise NotFoundError("Usuário não encontrado.")
        user.senha_hash = hash_password(nova_senha)
        log_service.record(
            session, LogAction.USER_UPDATED, actor, detalhes=f"senha alterada: {user.usuario}"
        )


def set_active(user_id: int, ativo: bool, actor: SessionUser) -> None:
    require(actor.role, Permission.USER_MANAGE)
    with session_scope() as session:
        repo = UserRepository(session)
        user = repo.get(user_id)
        if user is None:
            raise NotFoundError("Usuário não encontrado.")
        if not ativo and user.is_admin and _count_active_admins(repo) <= 1:
            raise BusinessError("É necessário manter ao menos um administrador ativo.")
        user.ativo = ativo
        log_service.record(
            session,
            LogAction.USER_UPDATED,
            actor,
            detalhes=f"{user.usuario}: {'ativado' if ativo else 'desativado'}",
        )


def _count_active_admins(repo: UserRepository) -> int:
    return sum(1 for user in repo.list_active() if user.is_admin and user.ativo)


def list_users(actor: SessionUser) -> list[UserRow]:
    require(actor.role, Permission.USER_MANAGE)
    with session_scope() as session:
        return [
            UserRow(
                id=user.id,
                usuario=user.usuario,
                nome=user.nome,
                papel=user.role.label,
                ativo=user.ativo,
                ultimo_acesso=user.ultimo_acesso,
            )
            for user in UserRepository(session).list_active()
        ]


def _to_session_user(user: User) -> SessionUser:
    return SessionUser(id=user.id, usuario=user.usuario, nome=user.nome, role=user.role)


__all__ = [
    "UserRow",
    "ValidationError",
    "authenticate",
    "change_password",
    "create_first_admin",
    "create_user",
    "has_admin",
    "list_users",
    "set_active",
]
