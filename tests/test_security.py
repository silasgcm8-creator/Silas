"""Senhas, papéis e permissões."""

from __future__ import annotations

import pytest

from app.models.status import Role
from app.security.authentication import AuthenticationError
from app.security.password import hash_password, verify_password
from app.security.permissions import Permission, PermissionDenied, can, require
from app.services import payment_service, user_service


def test_senha_nunca_fica_em_texto_puro():
    hash_value = hash_password("senha123")
    assert "senha123" not in hash_value
    assert verify_password("senha123", hash_value)
    assert not verify_password("senha124", hash_value)


def test_login_valido_e_invalido(admin):
    identidade = user_service.authenticate("admin", "senha123")
    assert identidade.usuario == "admin"
    assert identidade.is_admin

    with pytest.raises(AuthenticationError):
        user_service.authenticate("admin", "errada")


def test_funcionario_nao_desfaz_pagamento(admin):
    user_service.create_user("Ana Vendas", "ana", "senha123", Role.STAFF, admin)
    funcionario = user_service.authenticate("ana", "senha123")

    assert can(funcionario.role, Permission.PAYMENT_REGISTER)
    assert not can(funcionario.role, Permission.PAYMENT_UNDO)
    with pytest.raises(PermissionDenied):
        require(funcionario.role, Permission.BACKUP_RESTORE)
    with pytest.raises(PermissionDenied):
        payment_service.undo_payment(1, funcionario)


def test_usuario_duplicado(admin):
    from app.services.errors import BusinessError

    with pytest.raises(BusinessError):
        user_service.create_user("Outro", "admin", "senha123", Role.STAFF, admin)
