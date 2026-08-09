"""Validação e máscara de CPF."""

from __future__ import annotations

import pytest

from app.utils.cpf import format_cpf, is_valid_cpf, normalize_cpf, only_digits
from app.utils.validators import ValidationError, validate_cpf, validate_phone


def test_cpf_valido():
    assert is_valid_cpf("529.982.247-25")
    assert is_valid_cpf("52998224725")


@pytest.mark.parametrize(
    "valor",
    ["529.982.247-26", "111.111.111-11", "123", "", "abc.def.ghi-jk", "5299822472"],
)
def test_cpf_invalido(valor):
    assert not is_valid_cpf(valor)


def test_mascara_progressiva():
    assert format_cpf("529") == "529"
    assert format_cpf("529982") == "529.982"
    assert format_cpf("529982247") == "529.982.247"
    assert format_cpf("52998224725") == "529.982.247-25"
    assert only_digits("529.982.247-25") == "52998224725"


def test_normalizacao():
    assert normalize_cpf("52998224725") == "529.982.247-25"
    with pytest.raises(ValueError):
        normalize_cpf("529")


def test_validadores_lancam_mensagem_amigavel():
    with pytest.raises(ValidationError):
        validate_cpf("111.111.111-11")
    with pytest.raises(ValidationError):
        validate_phone("123")
    assert validate_phone("62998887766") == "(62) 99888-7766"
