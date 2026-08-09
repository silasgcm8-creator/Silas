"""Cadastro da empresa: identidade, logotipo e uso automático nos documentos."""

from __future__ import annotations

import pytest

from app.config import COMPANY_DEFAULT
from app.models.log import LogAction
from app.models.status import Role
from app.security.permissions import PermissionDenied
from app.services import company_service, log_service, user_service
from app.services.errors import BusinessError
from app.utils.cnpj import format_cnpj, format_document, is_valid_cnpj, is_valid_document

CNPJ = "11.222.333/0001-81"


def _logo(tmp_path, nome: str = "logo.png", tamanho: tuple[int, int] = (200, 200)):
    """Cria uma imagem de verdade para exercitar o cadastro do logotipo."""
    from PIL import Image

    caminho = tmp_path / nome
    # JPEG não guarda transparência; PNG/GIF guardam.
    modo = "RGB" if caminho.suffix.lower() in (".jpg", ".jpeg") else "RGBA"
    cor = (255, 255, 255) if modo == "RGB" else (255, 255, 255, 0)
    Image.new(modo, tamanho, cor).save(caminho)
    return caminho


# ---- validação de CNPJ ---------------------------------------------


def test_cnpj_valido_e_invalido():
    assert is_valid_cnpj(CNPJ)
    assert is_valid_cnpj("11444777000161")
    assert not is_valid_cnpj("11.222.333/0001-82")  # dígito trocado
    assert not is_valid_cnpj("11111111111111")
    assert not is_valid_cnpj("123")


def test_mascara_de_cnpj_progressiva():
    assert format_cnpj("11") == "11"
    assert format_cnpj("11222") == "11.222"
    assert format_cnpj("11222333") == "11.222.333"
    assert format_cnpj("112223330001") == "11.222.333/0001"
    assert format_cnpj("11222333000181") == CNPJ


def test_documento_aceita_cpf_e_cnpj():
    assert is_valid_document("529.982.247-25")
    assert is_valid_document(CNPJ)
    assert not is_valid_document("529.982.247-26")
    assert format_document("52998224725") == "529.982.247-25"
    assert format_document("11222333000181") == CNPJ


# ---- identidade fixa ------------------------------------------------


def test_documentos_usam_somente_otica_visao(admin):
    """Por decisão do proprietário, não há cadastro de dados da empresa."""
    assert COMPANY_DEFAULT == "Ótica Visão"
    perfil = company_service.profile()
    assert perfil.titulo == "ÓTICA VISÃO", "o topo do documento sai em maiúsculas"
    assert perfil.nome == "Ótica Visão"
    assert perfil.linhas_identificacao() == []


def test_nao_existe_cadastro_de_dados_da_empresa():
    """Razão social, CNPJ, endereço e telefone não são configuráveis."""
    for removido in ("save_profile", "company_settings", "save_company_settings"):
        assert not hasattr(company_service, removido)


# ---- logotipo -------------------------------------------------------


def test_logotipo_e_copiado_para_a_pasta_de_dados(admin, tmp_path):
    from app.config import settings

    origem = _logo(tmp_path)
    destino = company_service.save_logo(origem, admin)

    assert destino.parent == settings.data_dir
    assert destino.is_file()
    assert company_service.profile().tem_logo is True

    # Cópia, não referência: apagar o original não afeta os documentos.
    origem.unlink()
    assert company_service.profile().tem_logo is True


def test_trocar_o_formato_do_logotipo_nao_deixa_arquivo_orfao(admin, tmp_path):
    from app.config import settings

    company_service.save_logo(_logo(tmp_path, "a.png"), admin)
    company_service.save_logo(_logo(tmp_path, "b.jpg"), admin)

    restantes = sorted(p.name for p in settings.data_dir.glob("logotipo.*"))
    assert restantes == ["logotipo.jpg"]


def test_formato_de_imagem_nao_aceito(admin, tmp_path):
    ruim = tmp_path / "logo.bmp"
    ruim.write_bytes(b"nao importa")
    with pytest.raises(BusinessError, match="Formato"):
        company_service.save_logo(ruim, admin)


def test_arquivo_inexistente(admin, tmp_path):
    with pytest.raises(BusinessError):
        company_service.save_logo(tmp_path / "nao_existe.png", admin)


def test_remover_logotipo(admin, tmp_path):
    destino = company_service.save_logo(_logo(tmp_path), admin)
    company_service.remove_logo(admin)

    assert company_service.profile().tem_logo is False
    assert not destino.exists()


def test_logotipo_apagado_da_pasta_nao_quebra_o_documento(admin, tmp_path):
    """Se alguém apagar o arquivo por fora, o documento sai sem a marca."""
    destino = company_service.save_logo(_logo(tmp_path), admin)
    destino.unlink()

    perfil = company_service.profile()
    assert perfil.logo is None
    assert perfil.tem_logo is False


# ---- auditoria e permissões ----------------------------------------


def test_alteracao_do_logotipo_fica_na_auditoria(admin, tmp_path):
    from app.database.connection import session_scope

    company_service.save_logo(_logo(tmp_path), admin)
    company_service.remove_logo(admin)

    with session_scope() as session:
        acoes = [entry.acao for entry in log_service.latest(session)]
    assert acoes.count(LogAction.COMPANY_UPDATED) >= 2


def test_funcionario_nao_altera_dados_da_empresa(admin, tmp_path):
    user_service.create_user("Ana Vendas", "ana", "senha123", Role.STAFF, admin)
    funcionario = user_service.authenticate("ana", "senha123")

    with pytest.raises(PermissionDenied):
        company_service.save_logo(_logo(tmp_path), funcionario)
    with pytest.raises(PermissionDenied):
        company_service.remove_logo(funcionario)
