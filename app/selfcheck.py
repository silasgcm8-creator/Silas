"""Auto-verificação do programa — usada depois de gerar o executável.

O executável do Windows é montado por empacotamento: se faltar uma biblioteca,
o erro só aparece quando o funcionário clica no botão. Esta rotina exercita, em
poucos segundos e sem abrir janela, tudo que depende de biblioteca externa:

- banco de dados e migrações;
- interface (PySide6) e ícones;
- geração de PDF (comprovante, carnê e documento de cobrança);
- QR Code e código de barras;
- leitura de imagem do logotipo (Pillow);
- servidor local da consulta pelo celular (FastAPI);
- exportações (CSV sempre; Excel e PDF quando instalados);
- hash de senha (Argon2 ou bcrypt).

Rode ``SYS_Crediario.exe --verificar`` depois do build.
"""

from __future__ import annotations

import tempfile
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CheckResult:
    nome: str
    ok: bool
    detalhe: str = ""

    @property
    def marca(self) -> str:
        return "OK  " if self.ok else "FALHA"


def _check_database() -> str:
    from app.database.migrations import integrity_report, run_migrations

    run_migrations()
    ok, mensagens = integrity_report()
    if not ok:
        raise RuntimeError("; ".join(mensagens))
    from app.config import settings

    return f"banco em {settings.db_file}"


def _check_password() -> str:
    from app.security.password import algorithm, hash_password, verify_password

    hash_value = hash_password("verificacao")
    if not verify_password("verificacao", hash_value):
        raise RuntimeError("o hash gerado não confere com a senha")
    return f"algoritmo {algorithm()}"


def _check_interface() -> str:
    """Importa a interface e desenha um ícone, sem abrir janela."""
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    # QApplication (e não QGuiApplication): a interface é feita de widgets, e
    # criar a classe menor deixaria o Qt sem suporte a janela para quem
    # reaproveitar esta instância depois.
    from PySide6.QtWidgets import QApplication

    from app.ui import icons
    from app.ui.theme import ACCENT

    if QApplication.instance() is None:
        QApplication([])  # necessário para rasterizar o ícone

    import app.ui.charges  # noqa: F401
    import app.ui.credits  # noqa: F401
    import app.ui.login_window  # noqa: F401
    import app.ui.main_window  # noqa: F401
    import app.ui.settings  # noqa: F401
    import app.ui.staff_home  # noqa: F401

    pixmap = icons.pixmap("shield", ACCENT, 32)
    if pixmap.isNull():
        raise RuntimeError("não foi possível desenhar os ícones")

    # Uma janela de verdade é montada e descartada: prova que os widgets do Qt
    # foram empacotados, não só importados.
    from PySide6.QtWidgets import QWidget

    janela = QWidget()
    janela.setWindowTitle("verificacao")
    janela.deleteLater()

    from PySide6 import __version__ as pyside_version

    return f"PySide6 {pyside_version}"


def _check_pdf(pasta: Path) -> str:
    """Gera um PDF com texto, QR Code e código de barras."""
    from reportlab.graphics import renderPDF
    from reportlab.graphics.barcode import createBarcodeDrawing
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    destino = pasta / "verificacao.pdf"
    pdf = canvas.Canvas(str(destino), pagesize=A4)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, 800, "Verificação do SYS CREDIÁRIO — ÓTICA VISÃO")
    renderPDF.draw(
        createBarcodeDrawing("QR", value="OTICAVISAO:COB:OV-000000", width=80, height=80),
        pdf,
        40,
        680,
    )
    renderPDF.draw(
        createBarcodeDrawing("Code128", value="OV-000000", barHeight=30), pdf, 160, 700
    )
    pdf.showPage()
    pdf.save()

    conteudo = destino.read_bytes()
    if not conteudo.startswith(b"%PDF") or not conteudo.rstrip().endswith(b"%%EOF"):
        raise RuntimeError("o PDF gerado está incompleto")
    return f"{len(conteudo)} bytes, com QR e código de barras"


def _check_image() -> str:
    """Pillow: necessário para o logotipo entrar nos documentos."""
    from PIL import Image, __version__ as pillow_version

    with tempfile.TemporaryDirectory() as pasta:
        caminho = Path(pasta) / "logo.png"
        Image.new("RGBA", (32, 32), (255, 255, 255, 0)).save(caminho)
        with Image.open(caminho) as imagem:
            imagem.load()
    return f"Pillow {pillow_version}"


def _check_pix() -> str:
    from app.utils.pix import build_payload, crc16, is_valid_payload

    if crc16("123456789") != "29B1":
        raise RuntimeError("o cálculo do CRC do Pix está incorreto")
    payload = build_payload("teste@oticavisao.com.br", "OTICA VISAO", "GOIANIA", "10.00")
    if not is_valid_payload(payload):
        raise RuntimeError("o copia e cola gerado é inválido")
    return "copia e cola e CRC conferidos"


def _check_api() -> str:
    from app.api.server import create_app, local_ip

    rotas = {rota.path for rota in create_app().routes}
    if "/auth/login" not in rotas:
        raise RuntimeError("a API local não montou as rotas")
    return f"{len(rotas)} rotas, IP local {local_ip()}"


def _check_exports() -> str:
    from app.utils.export import available_formats, enable_optional_exporters, export

    enable_optional_exporters()
    formatos = available_formats()
    with tempfile.TemporaryDirectory() as pasta:
        for formato in formatos:
            export(formato, Path(pasta) / f"teste.{formato}", ["A", "B"], [("1", "2")])
    return ", ".join(formatos)


def _check_documents(pasta: Path) -> str:
    """Emite comprovante, carnê e cobrança de verdade, num banco temporário."""
    from datetime import date

    from app.services import (
        charge_service,
        client_service,
        credit_service,
        payment_service,
        receipt_service,
        slip_service,
        user_service,
    )

    import secrets

    if user_service.has_admin():  # pragma: no cover - proteção extra
        return "pulado: este banco já tem usuários (verificação não mexe em dados)"

    # Senha aleatória e descartável: o banco é temporário e some ao final, mas
    # nem por acidente deve existir uma credencial previsível no código.
    actor = user_service.create_first_admin(
        "Verificacao do sistema", "verificacao", secrets.token_urlsafe(18)
    )

    cliente = client_service.create_client(
        "Cliente de Verificacao", "529.982.247-25", "(62) 99888-7766", actor
    )
    crediario = credit_service.create_credit(
        cliente, "300,00", "0,00", 3, date.today(), "Verificação", actor
    )
    parcelas = credit_service.get_detail(crediario).installments

    # Cobrança, pagamento e comprovante são da **mesma** parcela: é assim que a
    # operação acontece no balcão, e o serviço recusa documento de outra parcela.
    documento, cobranca, _ = charge_service.create_and_issue(
        parcelas[0].id, destination=pasta / "cobranca.pdf", actor=actor
    )
    carne, _ = slip_service.issue(crediario, pasta / "carne.pdf", actor=actor)
    pagamento = payment_service.mark_as_paid(
        parcelas[0].id, actor, forma_pagamento="DINHEIRO", documento_id=documento
    )
    comprovante, _ = receipt_service.issue(
        pagamento, pasta / "comprovante.pdf", actor=actor
    )

    tamanhos = [p.stat().st_size for p in (cobranca, carne, comprovante)]
    if min(tamanhos) < 1000:
        raise RuntimeError("algum documento saiu vazio")
    return f"cobrança, carnê e comprovante gerados ({sum(tamanhos)} bytes)"


def run(verbose: bool = True) -> list[CheckResult]:
    """Executa todas as verificações e devolve o resultado de cada uma."""
    with tempfile.TemporaryDirectory(prefix="sys_verificacao_") as temporario:
        pasta = Path(temporario)
        etapas: list[tuple[str, Callable[[], str]]] = [
            ("Banco de dados e migrações", _check_database),
            ("Senhas (Argon2 / bcrypt)", _check_password),
            ("Interface e ícones (PySide6)", _check_interface),
            ("Imagens do logotipo (Pillow)", _check_image),
            ("PDF, QR Code e código de barras", lambda: _check_pdf(pasta)),
            ("Pix copia e cola", _check_pix),
            ("Servidor local (celular)", _check_api),
            ("Exportações", _check_exports),
            ("Documentos do sistema", lambda: _check_documents(pasta)),
        ]

        resultados: list[CheckResult] = []
        for nome, funcao in etapas:
            try:
                resultados.append(CheckResult(nome, True, funcao() or ""))
            except Exception as exc:  # noqa: BLE001 - o objetivo é relatar
                detalhe = f"{type(exc).__name__}: {exc}"
                resultados.append(CheckResult(nome, False, detalhe))
                if verbose:
                    traceback.print_exc()
    return resultados


def _attach_windows_console() -> None:
    """No Windows, reconecta a saída ao Prompt de Comando que chamou o programa.

    O executável é compilado sem console (para não abrir janela preta no atalho
    da Área de Trabalho). Sem esta reconexão, `--verificar` rodaria em silêncio
    e o relatório não apareceria para quem instalou.
    """
    import sys

    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        ATTACH_PARENT_PROCESS = -1
        if not ctypes.windll.kernel32.AttachConsole(ATTACH_PARENT_PROCESS):
            return
        for fluxo, destino in (("stdout", "CONOUT$"), ("stderr", "CONOUT$")):
            try:
                setattr(sys, fluxo, open(destino, "w", encoding="utf-8", buffering=1))
            except OSError:  # pragma: no cover - console indisponível
                continue
    except Exception:  # noqa: BLE001 - nunca impedir a verificação
        return


def report(verbose: bool = True) -> int:
    """Imprime o relatório e devolve o código de saída (0 = tudo certo).

    O relatório também é gravado em arquivo, para o caso de o console não estar
    disponível (duplo clique no executável, por exemplo).
    """
    _attach_windows_console()
    from app.config import APP_NAME, APP_VERSION, COMPANY_DEFAULT

    print("=" * 62)
    print(f"  {APP_NAME} {APP_VERSION} — verificação da instalação")
    print(f"  Empresa nos documentos: {COMPANY_DEFAULT}")
    print("  Roda em uma área temporária: os dados da loja não são tocados.")
    print("=" * 62)

    resultados = run(verbose=verbose)
    for item in resultados:
        detalhe = f" — {item.detalhe}" if item.detalhe else ""
        print(f"  [{item.marca}] {item.nome}{detalhe}")

    falhas = [item for item in resultados if not item.ok]
    print("-" * 62)
    if falhas:
        print(f"  {len(falhas)} verificação(ões) falharam.")
        print("  O programa pode não funcionar corretamente nesta máquina.")
    else:
        print("  Tudo certo. O sistema está pronto para uso.")

    caminho = _save_report(resultados, falhas)
    if caminho is not None:
        print(f"  Relatório salvo em: {caminho}")
    return 1 if falhas else 0


def _save_report(resultados: list[CheckResult], falhas: list[CheckResult]) -> Path | None:
    """Grava o relatório em arquivo. Falhar aqui não invalida a verificação."""
    from datetime import datetime

    from app.config import APP_NAME, APP_VERSION

    try:
        import os

        from app.config import base_dir

        # Em modo verificação, `base_dir()` aponta para a área temporária; o
        # relatório precisa ir para a pasta real da loja.
        destino_real = os.environ.get("SYS_VERIFICACAO_DESTINO")
        raiz = Path(destino_real) if destino_real else base_dir()
        pasta = raiz / "logs"
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / "verificacao.txt"
        linhas = [
            f"{APP_NAME} {APP_VERSION} — verificação da instalação",
            f"Executada em {datetime.now():%d/%m/%Y %H:%M}",
            "",
            *(
                f"[{item.marca}] {item.nome}"
                + (f" — {item.detalhe}" if item.detalhe else "")
                for item in resultados
            ),
            "",
            f"{len(falhas)} falha(s)." if falhas else "Nenhuma falha.",
        ]
        destino.write_text("\n".join(linhas), encoding="utf-8")
        return destino
    except OSError:  # pragma: no cover - pasta sem permissão
        return None
