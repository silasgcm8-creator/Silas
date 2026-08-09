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
        payment_service.reverse_payment(1, "tentativa indevida", funcionario)


def test_bloqueio_apos_seguidas_senhas_erradas(admin):
    """A API fica exposta no Wi-Fi: senha não pode ser testada sem limite."""
    from app.security.authentication import login_throttle

    for _ in range(login_throttle.max_attempts):
        with pytest.raises(AuthenticationError):
            user_service.authenticate("admin", "errada")

    # Agora nem a senha correta passa: a conta está temporariamente bloqueada.
    with pytest.raises(AuthenticationError, match="Muitas tentativas"):
        user_service.authenticate("admin", "senha123")

    assert login_throttle.locked_for("admin") > 0


def test_bloqueio_e_temporario_e_zera_no_acerto(admin):
    from app.security.authentication import login_throttle

    with pytest.raises(AuthenticationError):
        user_service.authenticate("admin", "errada")
    user_service.authenticate("admin", "senha123")

    # O acerto zera o contador, então erros anteriores não somam para o bloqueio.
    assert login_throttle.locked_for("admin") == 0
    for _ in range(login_throttle.max_attempts - 1):
        with pytest.raises(AuthenticationError, match="incorretos"):
            user_service.authenticate("admin", "errada")
    assert login_throttle.locked_for("admin") == 0


def test_usuario_duplicado(admin):
    from app.services.errors import BusinessError

    with pytest.raises(BusinessError):
        user_service.create_user("Outro", "admin", "senha123", Role.STAFF, admin)
