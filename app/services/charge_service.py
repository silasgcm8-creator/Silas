"""Documento de cobrança — uma parcela, pagamento presencial na loja.

Diferente do carnê (que mostra o parcelamento inteiro), este documento trata de
**uma parcela**: é o papel que o cliente leva ao caixa da Ótica Visão.

O QR Code impresso é **interno**: ele carrega apenas o código da cobrança, para
o atendente localizar a parcela no próprio sistema. Não é Pix e não é boleto
bancário — o documento declara isso de forma explícita.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.config import APP_NAME, APP_VERSION, settings
from app.database.connection import session_scope
from app.models.log import LogAction
from app.security.authentication import SessionUser
from app.security.permissions import Permission, require
from app.services import company_service, credit_service, log_service
from app.services.document_header import draw_header
from app.services.errors import BusinessError, NotFoundError
from app.services.receipt_service import mask_cpf
from app.utils.dates import format_br
from app.utils.money import format_brl

TITLE = "DOCUMENTO DE COBRANÇA"
SUBTITLE = "PAGAMENTO EXCLUSIVO NA LOJA"

#: Prefixo do conteúdo do QR interno. Deixa claro, para quem escanear com o
#: celular, que é uma referência do sistema e não um pagamento.
QR_PREFIX = "OTICA-VISAO/COBRANCA"

INSTRUCTION = (
    "Apresente este documento no caixa para realizar o pagamento."
)


def payment_notice(company: str) -> str:
    return (
        f"Este documento deverá ser pago diretamente na {company}. "
        "Apresente-o no caixa no momento do pagamento."
    )


def qr_disclaimer(company: str) -> str:
    return (
        "Este QR Code serve exclusivamente para localização da cobrança dentro "
        f"do sistema da {company} e não representa PIX ou boleto bancário."
    )


@dataclass(frozen=True)
class ChargeData:
    """Tudo que sai impresso no documento de cobrança."""

    codigo: str
    crediario_id: int
    parcela_id: int
    cliente: str
    cpf_mascarado: str
    telefone: str
    parcela: str
    vencimento: date
    valor: Decimal
    situacao: str
    dias_atraso: int
    descricao: str
    saldo_crediario: Decimal
    emitido_em: date

    @property
    def qr_content(self) -> str:
        return f"{QR_PREFIX}/{self.codigo}"

    @property
    def nome_arquivo(self) -> str:
        return f"Cobranca_{self.codigo}.pdf"


def charge_code(credit_id: int, numero: int) -> str:
    """Código da cobrança no formato 000123-03 (crediário e parcela)."""
    return f"{credit_id:06d}-{numero:02d}"


def parse_charge_code(codigo: str) -> tuple[int, int] | None:
    """Lê um código de cobrança. Devolve (crediário, parcela) ou None."""
    texto = (codigo or "").strip().upper()
    if texto.startswith(QR_PREFIX):
        texto = texto[len(QR_PREFIX) :].lstrip("/")
    partes = texto.split("-")
    if len(partes) != 2 or not all(p.isdigit() for p in partes):
        return None
    return int(partes[0]), int(partes[1])


def find_by_code(codigo: str) -> ChargeData | None:
    """Localiza a cobrança pelo código — é para isso que serve o QR interno."""
    lido = parse_charge_code(codigo)
    if lido is None:
        return None
    credit_id, numero = lido
    try:
        detail = credit_service.get_detail(credit_id)
    except NotFoundError:
        return None
    for item in detail.installments:
        if item.numero == numero:
            return build_charge(item.id)
    return None


def build_charge(installment_id: int) -> ChargeData:
    """Reúne os dados da parcela para o documento de cobrança."""
    detail, item = credit_service.find_installment(installment_id)
    return ChargeData(
        codigo=charge_code(detail.id, item.numero),
        crediario_id=detail.id,
        parcela_id=item.id,
        cliente=detail.cliente,
        cpf_mascarado=mask_cpf(detail.cpf),
        telefone=detail.telefone,
        # Zero à esquerda como no modelo aprovado: 03/10.
        parcela=f"{item.numero:02d}/{item.total:02d}",
        vencimento=item.vencimento,
        valor=item.valor,
        situacao=item.status,
        dias_atraso=item.dias_atraso,
        descricao=detail.descricao or "",
        saldo_crediario=detail.saldo,
        emitido_em=date.today(),
    )


def default_path(data: ChargeData) -> Path:
    pasta = settings.receipt_dir
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / data.nome_arquivo


def render_pdf(data: ChargeData, destination: Path | str | None = None) -> Path:
    """Desenha o documento de cobrança em A4."""
    try:
        from reportlab.graphics import renderPDF
        from reportlab.graphics.barcode import createBarcodeDrawing
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except ImportError as exc:  # pragma: no cover - depende da instalação
        raise BusinessError(
            "Para gerar o documento em PDF instale a biblioteca reportlab:\n"
            "python -m pip install reportlab"
        ) from exc

    company = company_service.profile()
    target = Path(destination) if destination else default_path(data)
    target.parent.mkdir(parents=True, exist_ok=True)

    largura, altura = A4
    margem = 18 * mm
    pdf = canvas.Canvas(str(target), pagesize=A4)
    pdf.setTitle(f"Cobrança {data.codigo}")
    pdf.setAuthor(company.titulo)

    y = draw_header(
        pdf,
        company,
        TITLE,
        SUBTITLE,
        largura=largura,
        margem=margem,
        topo=altura - margem,
    )

    pdf.setFont("Helvetica", 8.5)
    pdf.drawRightString(largura - margem, y, f"Emitido em {format_br(data.emitido_em)}")
    y -= 6 * mm

    # ---- dados da cobrança -----------------------------------------
    linhas = [
        ("Cliente", data.cliente),
        ("CPF", data.cpf_mascarado),
        ("Crediário", f"{data.crediario_id:06d}"),
        ("Parcela", data.parcela),
        ("Vencimento", format_br(data.vencimento)),
    ]
    if data.descricao:
        linhas.append(("Compra", data.descricao[:60]))

    for rotulo, valor in linhas:
        pdf.setFont("Helvetica", 10)
        pdf.drawString(margem, y, f"{rotulo}:")
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(margem + 30 * mm, y, str(valor))
        y -= 6 * mm

    y -= 3 * mm

    # ---- valor a pagar em destaque ---------------------------------
    caixa_altura = 22 * mm
    pdf.setLineWidth(1.2)
    pdf.rect(margem, y - caixa_altura, largura - 2 * margem, caixa_altura)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(margem + 4 * mm, y - 7 * mm, "VALOR A PAGAR")
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(margem + 4 * mm, y - 17 * mm, format_brl(data.valor))

    pdf.setFont("Helvetica-Bold", 10)
    if data.situacao == "ATRASADO":
        pdf.setFillColor(colors.HexColor("#B00020"))
        situacao = f"ATRASADO — {data.dias_atraso} dias"
    elif data.situacao == "PAGO":
        pdf.setFillColor(colors.HexColor("#1B7F3B"))
        situacao = "PAGO"
    else:
        situacao = "EM ABERTO"
    pdf.drawRightString(largura - margem - 4 * mm, y - 12 * mm, situacao)
    pdf.setFillColor(colors.black)
    y -= caixa_altura + 9 * mm

    # ---- pagamento presencial --------------------------------------
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margem, y, f"PAGAMENTO EXCLUSIVO NA {company.titulo}")
    y -= 6 * mm
    pdf.setFont("Helvetica", 9.5)
    for linha in _wrap(payment_notice(company.nome), 96):
        pdf.drawString(margem, y, linha)
        y -= 4.6 * mm
    y -= 1 * mm
    pdf.setFont("Helvetica-Bold", 9.5)
    pdf.drawString(margem, y, INSTRUCTION)
    y -= 10 * mm

    # ---- código e QR interno ---------------------------------------
    pdf.setFont("Helvetica", 10)
    pdf.drawString(margem, y, "Código da cobrança:")
    pdf.setFont("Courier-Bold", 13)
    pdf.drawString(margem + 38 * mm, y, data.codigo)
    y -= 8 * mm

    qr_lado = 32 * mm
    qr = createBarcodeDrawing("QR", value=data.qr_content, width=qr_lado, height=qr_lado)
    renderPDF.draw(qr, pdf, margem, y - qr_lado)

    texto_x = margem + qr_lado + 6 * mm
    ty = y - 5 * mm
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(texto_x, ty, "QR CODE INTERNO")
    ty -= 5 * mm
    pdf.setFont("Helvetica", 8)
    for linha in _wrap(qr_disclaimer(company.nome), 62):
        pdf.drawString(texto_x, ty, linha)
        ty -= 3.8 * mm

    ty -= 2 * mm
    pdf.setFont("Helvetica", 8)
    pdf.drawString(texto_x, ty, f"Saldo do crediário: {format_brl(data.saldo_crediario)}")

    # ---- rodapé -----------------------------------------------------
    base = margem + 6 * mm
    pdf.setLineWidth(0.5)
    pdf.line(margem, base + 10 * mm, largura - margem, base + 10 * mm)
    pdf.setFont("Helvetica", 7)
    pdf.drawString(
        margem,
        base + 6 * mm,
        "Documento de controle emitido pela própria loja. Não é boleto bancário "
        "e não pode ser pago em banco, lotérica ou aplicativo bancário.",
    )
    pdf.setFont("Helvetica", 6.5)
    pdf.drawString(margem, base + 2 * mm, f"{APP_NAME} {APP_VERSION}")

    pdf.showPage()
    pdf.save()
    return target


def _wrap(texto: str, largura: int) -> list[str]:
    if len(texto) <= largura:
        return [texto]
    linhas: list[str] = []
    atual = ""
    for palavra in texto.split(" "):
        if len(atual) + len(palavra) + 1 > largura:
            linhas.append(atual)
            atual = palavra
        else:
            atual = f"{atual} {palavra}".strip()
    if atual:
        linhas.append(atual)
    return linhas


def issue(
    installment_id: int,
    destination: Path | str | None = None,
    actor: SessionUser | None = None,
) -> tuple[Path, ChargeData]:
    """Emite o documento de cobrança e registra a emissão na auditoria."""
    if actor:
        require(actor.role, Permission.CHARGE_ISSUE)
    data = build_charge(installment_id)
    caminho = render_pdf(data, destination)

    with session_scope() as session:
        log_service.record(
            session,
            LogAction.CHARGE_ISSUED,
            actor,
            detalhes=(
                f"{data.cliente} — parcela {data.parcela} de "
                f"{format_brl(data.valor)} — cobrança {data.codigo}"
            ),
            crediario_id=data.crediario_id,
            parcela_id=data.parcela_id,
        )
    return caminho, data
