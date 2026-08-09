"""Permissões por papel."""

from __future__ import annotations

from enum import Enum

from app.models.status import Role


class Permission(str, Enum):
    CLIENT_VIEW = "cliente.ver"
    CLIENT_CREATE = "cliente.criar"
    CLIENT_EDIT = "cliente.editar"
    CLIENT_DELETE = "cliente.excluir"
    CREDIT_VIEW = "crediario.ver"
    CREDIT_CREATE = "crediario.criar"
    PAYMENT_REGISTER = "pagamento.registrar"
    PAYMENT_UNDO = "pagamento.estornar"
    RECEIPT_ISSUE = "comprovante.emitir"
    SLIP_ISSUE = "carne.emitir"
    CHARGE_ISSUE = "cobranca.emitir"
    CHARGE_CANCEL = "cobranca.cancelar"
    CHARGE_VIEW = "cobranca.ver"
    BANK_MANAGE = "banco.gerenciar"
    WHATSAPP = "whatsapp.abrir"
    REPORT_VIEW = "relatorio.ver"
    REPORT_FULL = "relatorio.completo"
    BACKUP_CREATE = "backup.criar"
    BACKUP_RESTORE = "backup.restaurar"
    USER_MANAGE = "usuario.gerenciar"
    LOG_VIEW = "log.ver"
    DB_CHECK = "banco.verificar"
    SETTINGS = "configuracao.alterar"
    API_CONTROL = "api.controlar"


STAFF_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.CLIENT_VIEW,
        Permission.CLIENT_CREATE,
        Permission.CLIENT_EDIT,
        Permission.CREDIT_VIEW,
        Permission.CREDIT_CREATE,
        Permission.PAYMENT_REGISTER,
        Permission.RECEIPT_ISSUE,
        Permission.SLIP_ISSUE,
        Permission.CHARGE_ISSUE,
        Permission.CHARGE_VIEW,
        Permission.WHATSAPP,
        Permission.REPORT_VIEW,
        Permission.BACKUP_CREATE,
    }
)

ADMIN_PERMISSIONS: frozenset[Permission] = frozenset(Permission)

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: ADMIN_PERMISSIONS,
    Role.STAFF: STAFF_PERMISSIONS,
}


class PermissionDenied(Exception):
    """Ação não permitida para o papel do usuário autenticado."""


def permissions_for(role: Role) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(role, STAFF_PERMISSIONS)


def can(role: Role, permission: Permission) -> bool:
    return permission in permissions_for(role)


def require(role: Role, permission: Permission) -> None:
    if not can(role, permission):
        raise PermissionDenied(
            "Seu usuário não possui permissão para esta ação. "
            "Solicite a um administrador."
        )
