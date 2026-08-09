"""Empacotamento para Windows: o que quebra o executável e não o código-fonte.

Estes testes existem porque cada item aqui já falhou de verdade no executável
enquanto funcionava perfeitamente rodando pelo código-fonte.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SPEC = RAIZ / "SYS_Crediario.spec"
BATS = ("build_exe.bat", "criar_atalho.bat", "verificar.bat")


# ---- receita do PyInstaller -----------------------------------------


def test_spec_existe_e_e_python_valido():
    assert SPEC.is_file(), "a receita do empacotamento precisa estar versionada"
    compile(SPEC.read_text(encoding="utf-8"), str(SPEC), "exec")


def test_barcode_do_reportlab_e_coletado_inteiro():
    """Sem isso o executável falha em todo PDF com QR ou código de barras.

    `reportlab/graphics/barcode/widgets.py` monta os widgets com `rl_exec` sobre
    o nome do módulo em string; a análise estática do PyInstaller não vê.
    """
    conteudo = SPEC.read_text(encoding="utf-8")
    assert 'collect_submodules("reportlab")' in conteudo


def test_modulos_resolvidos_em_tempo_de_execucao_estao_declarados():
    conteudo = SPEC.read_text(encoding="utf-8")
    for modulo in (
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.lifespan.on",
        "sqlalchemy.dialects.sqlite",
        "argon2",
        "bcrypt",
        "openpyxl",
        "PySide6.QtSvg",
        "PIL.PngImagePlugin",
        "PIL.JpegImagePlugin",
    ):
        assert f'"{modulo}"' in conteudo, f"{modulo} precisa estar no spec"


def _hidden_imports() -> set[str]:
    """Nomes declarados como hidden import, sem pegar a lista de exclusões."""
    conteudo = SPEC.read_text(encoding="utf-8")
    trecho = conteudo[: conteudo.index("EXCLUDES")]
    return set(re.findall(r'"((?:uvicorn|sqlalchemy|PIL|PySide6)[\w.]*)"', trecho))


def test_declaracoes_do_spec_sao_realmente_importaveis():
    """Um nome errado no spec só apareceria como falha no executável final."""
    import importlib

    nomes = _hidden_imports()
    assert nomes, "o spec deveria declarar módulos de tempo de execução"
    for nome in sorted(nomes):
        importlib.import_module(nome)


def test_hidden_imports_e_exclusoes_nao_se_contradizem():
    """Declarar e excluir o mesmo módulo deixaria o build imprevisível."""
    conteudo = SPEC.read_text(encoding="utf-8")
    excluidos = set(re.findall(r'"([\w.]+)"', conteudo[conteudo.index("EXCLUDES") :]))
    assert _hidden_imports().isdisjoint(excluidos)


def test_executavel_nao_carrega_peso_morto():
    conteudo = SPEC.read_text(encoding="utf-8")
    for excluido in ("tkinter", "PySide6.QtWebEngineCore", "pytest", "matplotlib"):
        assert f'"{excluido}"' in conteudo


def test_banco_nao_entra_no_executavel():
    """Os dados moram fora do programa: atualizar o .exe não pode apagá-los."""
    conteudo = SPEC.read_text(encoding="utf-8")
    datas = re.search(r"datas=\[(.*?)\]", conteudo, re.S)
    assert datas is not None
    assert ".db" not in datas.group(1)
    assert "data" not in datas.group(1).replace("datas", "")


def test_icone_do_executavel_existe_com_varios_tamanhos():
    icone = RAIZ / "assets" / "icone.ico"
    assert icone.is_file(), "o executável precisa de ícone próprio"

    from PIL import Image

    with Image.open(icone) as imagem:
        tamanhos = set(imagem.info.get("sizes", []))
    # 16 para a barra de tarefas, 256 para a Área de Trabalho em telas grandes.
    assert (16, 16) in tamanhos
    assert (256, 256) in tamanhos


# ---- scripts do Windows ---------------------------------------------


@pytest.mark.parametrize("nome", BATS)
def test_bat_usa_fim_de_linha_crlf(nome: str):
    """`cmd.exe` erra ao interpretar blocos em .bat com fim de linha Unix."""
    dados = (RAIZ / nome).read_bytes()
    assert b"\r\n" in dados, f"{nome} precisa de CRLF"
    assert not re.search(rb"(?<!\r)\n", dados), f"{nome} tem linha sem CR"


def test_gitattributes_preserva_crlf_no_checkout():
    conteudo = (RAIZ / ".gitattributes").read_text(encoding="utf-8")
    assert "*.bat text eol=crlf" in conteudo


@pytest.mark.parametrize("nome", BATS)
def test_bat_e_ascii_puro(nome: str):
    """Acento em .bat depende da página de código do console; evitamos."""
    dados = (RAIZ / nome).read_bytes()
    nao_ascii = [b for b in dados if b > 127]
    assert not nao_ascii, f"{nome} tem caractere fora do ASCII"


def test_build_espera_o_programa_de_janela_terminar():
    """`cmd` não aguarda um executável sem console: sem `start /wait` o
    resultado da verificação seria ignorado."""
    conteudo = (RAIZ / "build_exe.bat").read_text(encoding="utf-8")
    assert 'start /wait "" "dist\\SYS_Crediario.exe" --verificar' in conteudo


def test_build_usa_o_spec_e_verifica_no_final():
    conteudo = (RAIZ / "build_exe.bat").read_text(encoding="utf-8")
    assert "SYS_Crediario.spec" in conteudo
    assert "--verificar" in conteudo
    assert "errorlevel" in conteudo, "o script precisa reagir a falha"


def test_atalho_suporta_caminho_com_espaco():
    """O script vai para arquivo .ps1: caminho com espaço não quebra a linha."""
    conteudo = (RAIZ / "criar_atalho.bat").read_text(encoding="utf-8")
    assert "-File" in conteudo
    assert "$lnk.Save()" in conteudo


# ---- auto-verificação -----------------------------------------------


def test_verificacao_roda_fora_da_pasta_da_loja():
    """`--verificar` nunca pode escrever no banco real nem deixar usuário."""
    conteudo = (RAIZ / "main.py").read_text(encoding="utf-8")
    assert 'os.environ["SYS_HOME"] = _SANDBOX' in conteudo
    assert "mkdtemp" in conteudo
    assert "shutil.rmtree(_SANDBOX" in conteudo


def test_verificacao_nao_usa_senha_previsivel():
    conteudo = (RAIZ / "app" / "selfcheck.py").read_text(encoding="utf-8")
    assert "secrets.token_urlsafe" in conteudo
    assert "verificacao123" not in conteudo, "credencial fixa no código"


def test_nome_da_pasta_de_dados_bate_com_o_config():
    """main.py repete o nome da pasta antes de poder importar app.config."""
    from app.config import APP_SLUG

    conteudo = (RAIZ / "main.py").read_text(encoding="utf-8")
    assert f'Path.home() / "{APP_SLUG}"' in conteudo


def test_verificacao_reconecta_o_console_no_windows():
    """O executável é sem console; sem isso o relatório sairia em silêncio."""
    conteudo = (RAIZ / "app" / "selfcheck.py").read_text(encoding="utf-8")
    assert "AttachConsole" in conteudo


def test_todas_as_etapas_da_verificacao_passam():
    """Roda a auto-verificação de verdade, como o build faz no final."""
    from app.selfcheck import run

    resultados = run(verbose=False)
    falhas = [item.nome for item in resultados if not item.ok]
    assert not falhas, f"etapas com falha: {falhas}"
    assert len(resultados) >= 9


def test_relatorio_da_verificacao_e_gravado(tmp_path, monkeypatch):
    from app.selfcheck import CheckResult, _save_report

    monkeypatch.setenv("SYS_VERIFICACAO_DESTINO", str(tmp_path))
    destino = _save_report([CheckResult("Teste", True, "ok")], [])

    assert destino is not None
    conteudo = destino.read_text(encoding="utf-8")
    assert "Teste" in conteudo
    assert "Nenhuma falha." in conteudo
