"""Carnê de pagamento — demonstrativo do parcelamento em PDF, 100% offline.

O documento reúne todas as parcelas do crediário, com vencimento, valor e
situação, e reserva as áreas de pagamento:

- **Pix**: quando o administrador cadastra a chave Pix da empresa, o carnê sai
  com o *copia e cola* e o QR Code gerados aqui, a partir do padrão aberto do
  Banco Central. O dinheiro vai para a conta da própria empresa.
- **Código de barras**: uma área reservada, para a empresa colar a linha
  digitável emitida pelo banco dela. O sistema imprime nesse espaço apenas um
  código de barras **de controle interno** (o número do documento), útil para
  conferência no balcão.

Este carnê **não é um boleto bancário**: só um banco pode emitir um título
cobrável na rede bancária. O documento diz isso de forma clara no rodapé, para
que ninguém o confunda com uma cobrança registrada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.config import APP_NAME, APP_VERSION, COMPANY_DEFAULT, settings
from app.database.connection import session_scope
from app.database.migrations import KEY_COMPANY
from app.models.log import LogAction
from app.models.setting import Setting
from app.security.authentication import SessionUser
from app.security.permissions import Permission, require
from app.services import credit_service, log_service
from app.services.errors import BusinessError
from app.services.receipt_service import mask_cpf
from app.utils.dates import format_br
from app.utils.money import ZERO, format_brl
from app.utils.pix import build_payload

KEY_PIX = "empresa.pix_chave"
KEY_PIX_CITY = "empresa.pix_cidade"

#: Texto fixo do rodapé. Deixa explícito o que o documento é e o que não é.
DISCLAIMER = (
    "Documento de controle do crediário, emitido pela própria empresa. "
    "Não é um boleto bancário e não pode ser pago em banco, lotérica ou "
    "aplicativo bancário pela leitura do código de barras impresso nele."
)


@dataclass(frozen=True)
class SlipInstallment:
    numero: str
    vencimento: date
    valor: Decimal
    situacao: str


@dataclass(frozen=True)
class SlipData:
    """Tudo que sai impresso no carnê."""

    documento: str
    empresa: str
    cliente: str
    cpf_mascarado: str
    telefone: str
    crediario_id: int
    descricao: str
    valor_total: Decimal
    entrada: Decimal
    financiado: Decimal
    total_pago: Decimal
    saldo: Decimal
    vencido: Decimal
    emitido_em: date
    installments: list[SlipInstallment] = field(default_factory=list)
    pix_payload: str = ""
    pix_chave: str = ""

    @property
    def tem_pix(self) -> bool:
        return bool(self.pix_payload)

    @property
    def nome_arquivo(self) -> str:
        return f"Carne_{self.documento}.pdf"


def _setting(key: str, default: str = "") -> str:
    with session_scope() as session:
        row = session.get(Setting, key)
        return (row.valor if row else "") or default


def company_settings() -> tuple[str, str, str]:
    """Nome da empresa, chave Pix e cidade — o que sai impresso nos documentos."""
    return _setting(KEY_COMPANY, COMPANY_DEFAULT), _setting(KEY_PIX), _setting(KEY_PIX_CITY)


def pix_settings() -> tuple[str, str]:
    """Chave Pix e cidade cadastradas pela empresa."""
    return _setting(KEY_PIX), _setting(KEY_PIX_CITY)


def save_company_settings(
    nome: str, chave: str, cidade: str, actor: SessionUser | None = None
) -> tuple[str, str, str]:
    """Grava nome da empresa e dados do Pix (só administrador)."""
    if actor:
        require(actor.role, Permission.SETTINGS)
    nome = " ".join((nome or "").split())
    if not nome:
        raise BusinessError("Informe o nome da empresa que sai nos documentos.")

    chave, cidade = save_pix_settings(chave, cidade, actor)
    with session_scope() as session:
        row = session.get(Setting, KEY_COMPANY)
        if row is None:
            session.add(Setting(chave=KEY_COMPANY, valor=nome[:120]))
        else:
            row.valor = nome[:120]
    return nome[:120], chave, cidade


def save_pix_settings(
    chave: str, cidade: str, actor: SessionUser | None = None
) -> tuple[str, str]:
    """Grava a chave Pix da empresa (só administrador)."""
    if actor:
        require(actor.role, Permission.SETTINGS)
    chave = (chave or "").strip()
    cidade = (cidade or "").strip()

    if chave:
        # Só validamos o formato mínimo: a chave é da empresa e quem confere de
        # verdade é o banco dela na hora do pagamento.
        if len(chave) < 5 or " " in chave:
            raise BusinessError(
                "Chave Pix inválida. Use CPF/CNPJ, e-mail, telefone ou chave "
                "aleatória, sem espaços."
            )

    with session_scope() as session:
        for key, valor in ((KEY_PIX, chave), (KEY_PIX_CITY, cidade)):
            row = session.get(Setting, key)
            if row is None:
                session.add(Setting(chave=key, valor=valor))
            else:
                row.valor = valor
    return chave, cidade


def build_slip(credit_id: int, include_pix_amount: bool = True) -> SlipData:
    """Reúne os dados do carnê a partir do crediário."""
    detail = credit_service.get_detail(credit_id)
    empresa = _setting(KEY_COMPANY, COMPANY_DEFAULT)
    chave, cidade = pix_settings()
    documento = f"CAR-{credit_id:06d}"

    # O Pix estático leva o saldo devedor; se estiver quitado, sai sem valor.
    valor_pix = detail.saldo if include_pix_amount and detail.saldo > ZERO else None
    payload = build_payload(chave, empresa, cidade, valor_pix, documento)

    return SlipData(
        documento=documento,
        empresa=empresa,
        cliente=detail.cliente,
        cpf_mascarado=mask_cpf(detail.cpf),
        telefone=detail.telefone,
        crediario_id=detail.id,
        descricao=detail.descricao or "—",
        valor_total=detail.valor_total,
        entrada=detail.entrada,
        financiado=detail.financiado,
        total_pago=detail.total_pago,
        saldo=detail.saldo,
        vencido=detail.vencido,
        emitido_em=date.today(),
        installments=[
            SlipInstallment(
                numero=item.rotulo,
                vencimento=item.vencimento,
                valor=item.valor,
                situacao=(
                    f"ATRASADO ({item.dias_atraso} dias)"
                    if item.status == "ATRASADO"
                    else item.status
                ),
            )
            for item in detail.installments
        ],
        pix_payload=payload,
        pix_chave=chave,
    )


def default_path(data: SlipData) -> Path:
    pasta = settings.receipt_dir
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / data.nome_arquivo


def render_pdf(data: SlipData, destination: Path | str | None = None) -> Path:
    """Desenha o carnê em A4 e devolve o caminho do arquivo."""
    try:
        from reportlab.graphics.barcode import createBarcodeDrawing
        from reportlab.graphics import renderPDF
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except ImportError as exc:  # pragma: no cover - depende da instalação
        raise BusinessError(
            "Para gerar o carnê em PDF instale a biblioteca reportlab:\n"
            "python -m pip install reportlab"
        ) from exc

    target = Path(destination) if destination else default_path(data)
    target.parent.mkdir(parents=True, exist_ok=True)

    largura, altura = A4
    margem = 18 * mm
    pdf = canvas.Canvas(str(target), pagesize=A4)
    pdf.setTitle(f"Carnê {data.documento}")
    pdf.setAuthor(data.empresa)

    y = altura - margem

    # ---- cabeçalho -------------------------------------------------
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(margem, y, data.empresa[:48])
    pdf.setFont("Helvetica", 8.5)
    pdf.drawRightString(largura - margem, y, f"Documento {data.documento}")
    y -= 7 * mm
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(margem, y, "CARNÊ DE PAGAMENTO")
    pdf.setFont("Helvetica", 8.5)
    pdf.drawRightString(largura - margem, y, f"Emitido em {format_br(data.emitido_em)}")
    y -= 5 * mm
    pdf.setFont("Helvetica", 9)
    pdf.drawString(margem, y, "Demonstrativo do parcelamento")
    y -= 4 * mm
    pdf.setLineWidth(1)
    pdf.line(margem, y, largura - margem, y)
    y -= 7 * mm

    # ---- cliente e crediário ---------------------------------------
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(margem, y, data.cliente)
    pdf.setFont("Helvetica", 9)
    pdf.drawRightString(largura - margem, y, f"Crediário nº {data.crediario_id}")
    y -= 5 * mm
    pdf.drawString(margem, y, f"CPF {data.cpf_mascarado}   |   Telefone {data.telefone}")
    y -= 5 * mm
    if data.descricao != "—":
        pdf.drawString(margem, y, f"Compra: {data.descricao[:70]}")
        y -= 5 * mm

    resumo = (
        f"Valor total {format_brl(data.valor_total)}   |   "
        f"Entrada {format_brl(data.entrada)}   |   "
        f"Financiado {format_brl(data.financiado)}   |   "
        f"{len(data.installments)}x"
    )
    pdf.setFont("Helvetica", 9)
    pdf.drawString(margem, y, resumo)
    y -= 8 * mm

    # ---- tabela de parcelas ----------------------------------------
    colunas = (margem, margem + 26 * mm, margem + 62 * mm, margem + 100 * mm)
    pdf.setFont("Helvetica-Bold", 9)
    for rotulo, x in zip(("PARCELA", "VENCIMENTO", "VALOR", "SITUAÇÃO"), colunas):
        pdf.drawString(x, y, rotulo)
    y -= 2 * mm
    pdf.setLineWidth(0.5)
    pdf.line(margem, y, largura - margem, y)
    y -= 5 * mm

    pdf.setFont("Helvetica", 9)
    for item in data.installments:
        if y < 95 * mm:  # deixa espaço para as áreas de pagamento
            pdf.showPage()
            y = altura - margem
            pdf.setFont("Helvetica", 9)
        pdf.drawString(colunas[0], y, item.numero)
        pdf.drawString(colunas[1], y, format_br(item.vencimento))
        pdf.drawString(colunas[2], y, format_brl(item.valor))
        if item.situacao.startswith("ATRASADO"):
            pdf.setFillColor(colors.HexColor("#B00020"))
        elif item.situacao == "PAGO":
            pdf.setFillColor(colors.HexColor("#1B7F3B"))
        pdf.drawString(colunas[3], y, item.situacao)
        pdf.setFillColor(colors.black)
        y -= 5.5 * mm

    y -= 2 * mm
    pdf.line(margem, y, largura - margem, y)
    y -= 6 * mm
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(
        margem,
        y,
        f"Pago {format_brl(data.total_pago)}   |   "
        f"Saldo devedor {format_brl(data.saldo)}   |   "
        f"Vencido {format_brl(data.vencido)}",
    )
    y -= 10 * mm

    # ---- áreas de pagamento ----------------------------------------
    caixa_altura = 46 * mm
    meio = largura / 2
    base = max(y - caixa_altura, margem + 24 * mm)

    pdf.setLineWidth(0.8)
    pdf.rect(margem, base, meio - margem - 4 * mm, caixa_altura)
    pdf.rect(meio + 4 * mm, base, largura - margem - meio - 4 * mm, caixa_altura)

    # Pix (esquerda)
    px = margem + 4 * mm
    py = base + caixa_altura - 6 * mm
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(px, py, "PAGAMENTO VIA PIX")
    py -= 5 * mm
    pdf.setFont("Helvetica", 8)

    if data.tem_pix:
        qr = createBarcodeDrawing("QR", value=data.pix_payload, width=30 * mm, height=30 * mm)
        renderPDF.draw(qr, pdf, px, base + 5 * mm)
        texto_x = px + 34 * mm
        pdf.drawString(texto_x, py, "Chave Pix:")
        py -= 3.6 * mm
        for pedaco in _wrap(data.pix_chave, 30):
            pdf.drawString(texto_x, py, pedaco)
            py -= 3.6 * mm
        if data.saldo > ZERO:
            pdf.drawString(texto_x, py, f"Valor: {format_brl(data.saldo)}")
            py -= 4 * mm
        pdf.drawString(texto_x, py, "Copia e cola:")
        py -= 3.5 * mm
        pdf.setFont("Courier", 5.4)
        # Blocos de tamanho fixo: o copia e cola tem espaços no nome da empresa
        # e quebrá-lo por palavra atrapalharia quem copia do PDF.
        for pedaco in _chunks(data.pix_payload, 34):
            pdf.drawString(texto_x, py, pedaco)
            py -= 2.6 * mm
    else:
        pdf.drawString(px, py, "Cadastre a chave Pix da empresa em")
        py -= 4 * mm
        pdf.drawString(px, py, "Configurações → Empresa e Pix para que o")
        py -= 4 * mm
        pdf.drawString(px, py, "QR Code e o copia e cola saiam aqui.")
        py -= 6 * mm
        pdf.setDash(2, 2)
        pdf.rect(px, base + 5 * mm, 30 * mm, 30 * mm)
        pdf.setDash()
        pdf.setFont("Helvetica", 7)
        pdf.drawString(px + 32 * mm, base + 20 * mm, "Espaço reservado")
        pdf.drawString(px + 32 * mm, base + 16 * mm, "para o QR Code Pix")

    # Código de barras (direita)
    bx = meio + 8 * mm
    by = base + caixa_altura - 6 * mm
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(bx, by, "CÓDIGO DE BARRAS")
    by -= 5 * mm
    pdf.setFont("Helvetica", 7.5)
    pdf.drawString(bx, by, "Área reservada para a linha digitável do banco")
    by -= 3.5 * mm
    pdf.drawString(bx, by, "da empresa, quando houver cobrança registrada.")
    by -= 6 * mm

    pdf.setDash(2, 2)
    pdf.rect(bx, by - 14 * mm, largura - margem - bx - 4 * mm, 14 * mm)
    pdf.setDash()

    codigo = createBarcodeDrawing(
        "Code128", value=data.documento, barHeight=11 * mm, humanReadable=True
    )
    renderPDF.draw(codigo, pdf, bx, base + 6 * mm)
    pdf.setFont("Helvetica", 6.5)
    pdf.drawString(bx, base + 3 * mm, "Código interno de conferência no balcão.")

    # ---- rodapé -----------------------------------------------------
    pdf.setFont("Helvetica", 7)
    rodape = base - 6 * mm
    for linha in _wrap(DISCLAIMER, 118):
        pdf.drawString(margem, rodape, linha)
        rodape -= 3.2 * mm
    pdf.setFont("Helvetica", 6.5)
    pdf.drawString(margem, rodape - 1 * mm, f"{APP_NAME} {APP_VERSION}")

    pdf.showPage()
    pdf.save()
    return target


def _chunks(texto: str, largura: int) -> list[str]:
    """Divide em blocos exatos de `largura` caracteres, sem olhar espaços."""
    return [texto[i : i + largura] for i in range(0, len(texto), largura)] or [""]


def _wrap(texto: str, largura: int) -> list[str]:
    """Quebra o texto em linhas de no máximo `largura` caracteres."""
    if len(texto) <= largura:
        return [texto]
    linhas: list[str] = []
    atual = ""
    for palavra in texto.split(" "):
        if len(palavra) > largura:  # cadeias longas (copia e cola) são cortadas
            if atual:
                linhas.append(atual)
                atual = ""
            linhas.extend(
                palavra[i : i + largura] for i in range(0, len(palavra), largura)
            )
            continue
        if len(atual) + len(palavra) + 1 > largura:
            linhas.append(atual)
            atual = palavra
        else:
            atual = f"{atual} {palavra}".strip()
    if atual:
        linhas.append(atual)
    return linhas


def issue(
    credit_id: int,
    destination: Path | str | None = None,
    actor: SessionUser | None = None,
) -> tuple[Path, SlipData]:
    """Emite o carnê e registra a emissão na auditoria."""
    if actor:
        require(actor.role, Permission.SLIP_ISSUE)
    data = build_slip(credit_id)
    caminho = render_pdf(data, destination)

    with session_scope() as session:
        log_service.record(
            session,
            LogAction.SLIP_ISSUED,
            actor,
            detalhes=(
                f"{data.cliente} — crediário {data.crediario_id} — "
                f"{len(data.installments)} parcela(s)"
                + (" — com Pix" if data.tem_pix else " — sem Pix cadastrado")
            ),
            crediario_id=data.crediario_id,
        )
    return caminho, data
