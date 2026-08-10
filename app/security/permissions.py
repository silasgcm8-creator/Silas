"""Permissões por papel.

Regra que sustenta o perfil FUNCIONÁRIO: qualquer número que descreva a
**situação financeira global da loja** (totais, somatórios, indicadores) ou
**inadimplência** (atrasos, dias em atraso, ranking de devedores) é protegido
por uma única permissão — ``FINANCE_OVERVIEW``. Uma permissão só, e não duas
parecidas, porque foi exatamente a existência de uma "versão fraca" desse
direito que deixou o painel financeiro aberto para o funcionário.

Quem precisa desses números conferir, confere: os serviços chamam ``require``
antes de tocar no banco. Esconder o botão na tela não é permissão.
"""

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
    #: Visão financeira global e inadimplência: painel, relatórios, atrasados,
    #: totais consolidados e qualquer somatório que ultrapasse o atendimento de
    #: um cliente. Exclusiva do administrador.
    FINANCE_OVERVIEW = "financeiro.visao_global"
    BACKUP_CREATE = "backup.criar"
    BACKUP_RESTORE = "backup.restaurar"
    USER_MANAGE = "usuario.gerenciar"
    LOG_VIEW = "log.ver"
    DB_CHECK = "banco.verificar"
    SETTINGS = "configuracao.alterar"
    API_CONTROL = "api.controlar"


#: O balcão: atender, cadastrar, receber e emitir documento. Nada que revele a
#: situação financeira da loja ou a inadimplência — nem o envio de cobrança por
#: WhatsApp, que expõe valor vencido e dias de atraso.
#:
#: `CHARGE_VIEW` fica de fora de propósito: é a tela de **gestão** de cobranças,
#: com filtros, histórico e os documentos de todos os clientes. O funcionário
#: emite e reimprime pela tela GERAR BOLETO, recebe pela REGISTRAR PAGAMENTO e
#: confere o próprio caixa em RECEBIMENTOS — cada uma trabalhando sobre um
#: cliente de cada vez.
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
