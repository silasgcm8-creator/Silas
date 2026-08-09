# -*- mode: python ; coding: utf-8 -*-
"""Receita de empacotamento do SYS CREDIÁRIO para Windows.

Ficar em arquivo (e não em linha de comando dentro do .bat) permite revisar o
que entra no executável e versionar as correções.

Pontos que exigem declaração explícita, porque o PyInstaller não descobre
sozinho:

- ``uvicorn`` escolhe protocolo e loop **em tempo de execução**, por nome;
- ``app.*`` tem serviços importados dentro de função (import tardio), então o
  pacote inteiro é coletado;
- ``openpyxl`` só é importado quando o usuário exporta;
- ``reportlab.graphics.barcode`` monta os widgets com ``rl_exec`` sobre uma
  string com o nome do módulo (ver ``barcode/widgets.py``, ``_BCW``). Nenhuma
  análise estática enxerga isso: sem coletar o pacote inteiro, o executável
  falha em **todo PDF com QR ou código de barras** — ou seja, no documento de
  cobrança e no carnê;
- ``PIL`` registra os leitores de imagem por plugin, ao abrir o arquivo.

O banco de dados **não** entra no executável: ele vive em
``%USERPROFILE%\\SYS_Crediario\\data``, para que atualizar o programa nunca
apague dados (ver ``app/config.py``).
"""

from PyInstaller.utils.hooks import collect_submodules

# Escolhe protocolo/loop por nome em tempo de execução.
UVICORN = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
]

# Leitores de imagem usados pelo logotipo dos documentos.
PILLOW = [
    "PIL.Image",
    "PIL.ImageFile",
    "PIL.PngImagePlugin",
    "PIL.JpegImagePlugin",
    "PIL.GifImagePlugin",
]

HIDDEN = [
    *collect_submodules("app"),
    # Ver a nota do topo: os widgets de código de barras são importados por
    # nome em tempo de execução. Coletar tudo é o que mantém o QR funcionando.
    *collect_submodules("reportlab"),
    *UVICORN,
    *PILLOW,
    # Dialeto do banco resolvido por URL, em texto.
    "sqlalchemy.dialects.sqlite",
    # Hash de senha: o módulo escolhe o disponível em tempo de execução.
    "argon2",
    "bcrypt",
    # Exportação opcional em Excel.
    "openpyxl",
    # Ícones do sistema são SVG desenhados em tempo de execução.
    "PySide6.QtSvg",
]

# Peso morto: o programa é desktop e offline, nada disso é usado.
EXCLUDES = [
    "tkinter",
    "PySide6.QtQuick",
    "PySide6.QtQml",
    "PySide6.Qt3DCore",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtMultimedia",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtOpenGL",
    "PySide6.QtTest",
    "matplotlib",
    "numpy",
    "pandas",
    "pytest",
    "IPython",
]

analysis = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    # O ícone acompanha o executável para o atalho da Área de Trabalho.
    datas=[("assets/icone.ico", "assets")],
    hiddenimports=HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="SYS_Crediario",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # Sem janela preta de terminal ao abrir pelo atalho. O modo --verificar
    # continua imprimindo no console quando chamado pelo Prompt de Comando.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icone.ico",
    version="version_info.txt",
)
