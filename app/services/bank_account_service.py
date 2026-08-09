"""Contas de recebimento — cadastro exclusivo do administrador.

O funcionário apenas **escolhe** uma conta já autorizada ao emitir a cobrança;
ele não cadastra nem altera dado bancário nenhum. Nada aqui é gerado pelo
sistema: todo campo vem digitado pelo administrador.
"""

from __future__ import annotations

from dataclasses import dataclass

import sqlalchemy as sa

from app.database.connection import session_scope
from app.models.bank_account import ACCOUNT_TYPES, PIX_KEY_TYPES, BankAccount
from app.models.log import LogAction
from app.security.authentication import SessionUser
from app.security.permissions import Permission, require
from app.services import log_service
from app.services.errors import BusinessError, NotFoundError
from app.utils.cnpj import format_document, is_valid_document


@dataclass(frozen=True)
class AccountRow:
    """Linha da lista de contas."""

    id: int
    identificacao: str
    banco: str
    agencia: str
    conta: str
    beneficiario: str
    documento: str
    pix: str
    pix_tipo: str
    tipo_conta: str
    ativa: bool

    @property
    def resumo(self) -> str:
        """Texto curto para o seletor da tela de cobrança."""
        partes = [p for p in (self.banco, self.agencia, self.conta) if p]
        if not partes and self.pix:
            partes = [f"PIX {self.pix}"]
        return f"{self.identificacao} — {' / '.join(partes)}" if partes else self.identificacao


def _to_row(account: BankAccount) -> AccountRow:
    return AccountRow(
        id=account.id,
        identificacao=account.identificacao,
        banco=account.banco_completo,
        agencia=account.agencia_completa,
        conta=account.conta_completa,
        beneficiario=account.beneficiario_nome,
        documento=account.beneficiario_documento,
        pix=account.pix_chave,
        pix_tipo=account.pix_tipo,
        tipo_conta=account.tipo_conta,
        ativa=account.ativa,
    )


def list_accounts(only_active: bool = True) -> list[AccountRow]:
    """Contas cadastradas. Por padrão, só as ativas (o que o balcão pode usar)."""
    with session_scope() as session:
        stmt = sa.select(BankAccount).order_by(BankAccount.identificacao)
        if only_active:
            stmt = stmt.where(BankAccount.ativa.is_(True))
        return [_to_row(account) for account in session.scalars(stmt).all()]


def get_account(account_id: int) -> AccountRow:
    with session_scope() as session:
        account = session.get(BankAccount, account_id)
        if account is None:
            raise NotFoundError("Conta de recebimento não encontrada.")
        return _to_row(account)


def _validate(
    identificacao: str,
    tipo_conta: str,
    beneficiario_documento: str,
    pix_tipo: str,
    banco_nome: str,
    conta: str,
    pix_chave: str,
) -> tuple[str, str]:
    if not identificacao.strip():
        raise BusinessError("Informe um nome de identificação para a conta.")
    if tipo_conta and tipo_conta not in ACCOUNT_TYPES:
        raise BusinessError(f"Tipo de conta inválido. Use: {', '.join(ACCOUNT_TYPES)}.")
    if pix_tipo and pix_tipo not in PIX_KEY_TYPES:
        raise BusinessError(f"Tipo de chave Pix inválido. Use: {', '.join(PIX_KEY_TYPES)}.")

    documento = beneficiario_documento.strip()
    if documento:
        if not is_valid_document(documento):
            raise BusinessError("CPF/CNPJ do beneficiário inválido.")
        documento = format_document(documento)

    # Uma conta sem banco e sem Pix não serve para receber nada.
    if not (banco_nome.strip() or conta.strip() or pix_chave.strip()):
        raise BusinessError(
            "Informe ao menos os dados do banco ou uma chave Pix — sem isso a "
            "conta não pode ser usada em uma cobrança."
        )
    return identificacao.strip(), documento


def create_account(
    identificacao: str,
    banco_nome: str = "",
    banco_codigo: str = "",
    agencia: str = "",
    agencia_digito: str = "",
    conta: str = "",
    conta_digito: str = "",
    tipo_conta: str = "",
    beneficiario_nome: str = "",
    beneficiario_documento: str = "",
    pix_chave: str = "",
    pix_tipo: str = "",
    carteira: str = "",
    convenio: str = "",
    codigo_beneficiario: str = "",
    actor: SessionUser | None = None,
) -> int:
    """Cadastra uma conta de recebimento (somente administrador)."""
    if actor:
        require(actor.role, Permission.BANK_MANAGE)
    identificacao, documento = _validate(
        identificacao, tipo_conta, beneficiario_documento, pix_tipo,
        banco_nome, conta, pix_chave,
    )

    with session_scope() as session:
        existente = session.scalar(
            sa.select(BankAccount).where(BankAccount.identificacao == identificacao)
        )
        if existente is not None:
            raise BusinessError(
                f"Já existe uma conta chamada '{identificacao}'. Use outro nome."
            )
        account = BankAccount(
            identificacao=identificacao,
            banco_nome=banco_nome.strip(),
            banco_codigo=banco_codigo.strip(),
            agencia=agencia.strip(),
            agencia_digito=agencia_digito.strip(),
            conta=conta.strip(),
            conta_digito=conta_digito.strip(),
            tipo_conta=tipo_conta.strip(),
            beneficiario_nome=beneficiario_nome.strip(),
            beneficiario_documento=documento,
            pix_chave=pix_chave.strip(),
            pix_tipo=pix_tipo.strip(),
            carteira=carteira.strip(),
            convenio=convenio.strip(),
            codigo_beneficiario=codigo_beneficiario.strip(),
        )
        session.add(account)
        session.flush()
        log_service.record(
            session,
            LogAction.BANK_ACCOUNT_CREATED,
            actor,
            detalhes=f"conta de recebimento: {identificacao}",
        )
        return account.id


def update_account(
    account_id: int, actor: SessionUser | None = None, **campos: str
) -> None:
    """Altera uma conta. Cada alteração fica registrada na auditoria."""
    if actor:
        require(actor.role, Permission.BANK_MANAGE)

    permitidos = {
        "identificacao", "banco_nome", "banco_codigo", "agencia", "agencia_digito",
        "conta", "conta_digito", "tipo_conta", "beneficiario_nome",
        "beneficiario_documento", "pix_chave", "pix_tipo", "carteira", "convenio",
        "codigo_beneficiario",
    }
    desconhecidos = set(campos) - permitidos
    if desconhecidos:
        raise BusinessError(f"Campos inválidos: {', '.join(sorted(desconhecidos))}.")

    with session_scope() as session:
        account = session.get(BankAccount, account_id)
        if account is None:
            raise NotFoundError("Conta de recebimento não encontrada.")

        novos = {chave: str(valor or "").strip() for chave, valor in campos.items()}
        identificacao, documento = _validate(
            novos.get("identificacao", account.identificacao),
            novos.get("tipo_conta", account.tipo_conta),
            novos.get("beneficiario_documento", account.beneficiario_documento),
            novos.get("pix_tipo", account.pix_tipo),
            novos.get("banco_nome", account.banco_nome),
            novos.get("conta", account.conta),
            novos.get("pix_chave", account.pix_chave),
        )
        novos["identificacao"] = identificacao
        if "beneficiario_documento" in novos:
            novos["beneficiario_documento"] = documento

        alterados = [
            chave for chave, valor in novos.items() if getattr(account, chave) != valor
        ]
        for chave, valor in novos.items():
            setattr(account, chave, valor)

        log_service.record(
            session,
            LogAction.BANK_ACCOUNT_UPDATED,
            actor,
            detalhes=f"{identificacao}: {', '.join(alterados) or 'sem alteração'}",
        )


def set_active(account_id: int, ativa: bool, actor: SessionUser | None = None) -> None:
    """Desativa (ou reativa) a conta. Desativada não aparece na cobrança."""
    if actor:
        require(actor.role, Permission.BANK_MANAGE)
    with session_scope() as session:
        account = session.get(BankAccount, account_id)
        if account is None:
            raise NotFoundError("Conta de recebimento não encontrada.")
        account.ativa = ativa
        log_service.record(
            session,
            LogAction.BANK_ACCOUNT_UPDATED,
            actor,
            detalhes=f"{account.identificacao}: {'ativada' if ativa else 'desativada'}",
        )


def delete_account(account_id: int, actor: SessionUser | None = None) -> None:
    """Exclui a conta. Se já houver cobrança usando, apenas desativa."""
    if actor:
        require(actor.role, Permission.BANK_MANAGE)
    from app.models.charge import ChargeDocument

    with session_scope() as session:
        account = session.get(BankAccount, account_id)
        if account is None:
            raise NotFoundError("Conta de recebimento não encontrada.")
        em_uso = session.scalar(
            sa.select(sa.func.count())
            .select_from(ChargeDocument)
            .where(ChargeDocument.conta_id == account_id)
        )
        nome = account.identificacao
        if em_uso:
            # Apagar destruiria a informação de documentos já emitidos.
            account.ativa = False
            detalhes = f"{nome}: desativada (usada em {em_uso} documento(s))"
        else:
            session.delete(account)
            detalhes = f"{nome}: excluída"
        log_service.record(
            session, LogAction.BANK_ACCOUNT_DELETED, actor, detalhes=detalhes
        )
