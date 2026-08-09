"""Comprovante de pagamento — geração em PDF, 100% offline.

O documento é montado com reportlab, que roda localmente: nenhuma chamada de
rede, nenhum serviço externo. Dois formatos são oferecidos, com exatamente o
mesmo conteúdo:

- ``A4``: folha inteira, para arquivo da empresa.
- ``COMPACTO``: 80 mm de largura, para impressora térmica de balcão.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from app.config import APP_NAME, APP_VERSION, COMPANY_DEFAULT, settings
from app.database.connection import session_scope
from app.models.log import LogAction
from app.repositories.payment_repository import PaymentRepository
from app.security.authentication import SessionUser
from app.security.permissions import Permission, require
from app.services import company_service, log_service
from app.services.document_header import draw_header
from app.services.errors import BusinessError, NotFoundError
from app.utils.dates import format_br, format_datetime_br
from app.utils.money import format_brl

A4 = "A4"
COMPACT = "COMPACTO"
FORMATS = (A4, COMPACT)


@dataclass(frozen=True)
class ReceiptData:
    """Tudo o que sai impresso no comprovante."""

    codigo: str
    empresa: str
    cliente: str
    cpf_mascarado: str
    telefone: str
    parcela: str
    vencimento: date
    valor: Decimal
    data_pagamento: date
    registrado_em: datetime
    funcionario: str
    situacao: str
    crediario_id: int

    def nome_arquivo(self, layout: str = A4) -> str:
        """Nome do arquivo. O formato entra no nome para os dois coexistirem."""
        sufixo = "" if layout == A4 else f"_{layout.lower()}"
        return f"Comprovante_{self.codigo}{sufixo}.pdf"


def mask_cpf(cpf: str) -> str:
    """Esconde o miolo do CPF: 529.***.**7-25.

    O cliente reconhece o próprio documento, mas o comprovante deixa de ser um
    papel com CPF completo circulando — coleta e exposição mínimas (LGPD).
    """
    digits = [c for c in (cpf or "") if c.isdigit()]
    if len(digits) != 11:
        return cpf or "—"
    d = "".join(digits)
    return f"{d[:3]}.***.**{d[8]}-{d[9:]}"


def _company_name() -> str:
    return company_service.profile().titulo


def build_receipt(payment_id: int) -> ReceiptData:
    """Reúne os dados do recebimento para o comprovante."""
    with session_scope() as session:
        row = PaymentRepository(session).receipt_data(payment_id)
    if row is None:
        raise NotFoundError("Recebimento não encontrado.")
    if row.estornado_em is not None:
        raise BusinessError(
            "Este recebimento foi estornado e não possui comprovante válido."
        )
    return ReceiptData(
        codigo=row.codigo or f"PAG-{payment_id:04d}",
        empresa=_company_name(),
        cliente=row.cliente,
        cpf_mascarado=mask_cpf(row.cpf),
        telefone=row.telefone,
        parcela=f"{row.numero}/{row.parcelas}",
        vencimento=row.vencimento,
        valor=row.valor,
        data_pagamento=row.data_pagamento,
        registrado_em=row.criado_em,
        funcionario=row.usuario_nome or "—",
        situacao="PAGO",
        crediario_id=row.crediario_id,
    )


def _lines(data: ReceiptData) -> list[tuple[str, str]]:
    return [
        ("Cliente", data.cliente),
        ("CPF", data.cpf_mascarado),
        ("Telefone", data.telefone),
        ("Crediário", f"nº {data.crediario_id}"),
        ("Parcela", data.parcela),
        ("Vencimento", format_br(data.vencimento)),
        ("Valor recebido", format_brl(data.valor)),
        ("Data do pagamento", format_br(data.data_pagamento)),
        ("Registrado em", format_datetime_br(data.registrado_em)),
        ("Identificador", data.codigo),
        ("Funcionário", data.funcionario),
        ("Status", data.situacao),
    ]


def default_path(data: ReceiptData, layout: str = A4) -> Path:
    pasta = settings.receipt_dir
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / data.nome_arquivo(layout)


def render_pdf(data: ReceiptData, destination: Path | str | None = None, layout: str = A4) -> Path:
    """Gera o PDF do comprovante e devolve o caminho do arquivo."""
    if layout not in FORMATS:
        raise BusinessError(f"Formato de comprovante desconhecido: {layout!r}")
    try:
        from reportlab.lib.pagesizes import A4 as A4_SIZE
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except ImportError as exc:  # pragma: no cover - depende da instalação
        raise BusinessError(
            "Para gerar o comprovante em PDF instale a biblioteca reportlab:\n"
            "python -m pip install reportlab"
        ) from exc

    target = Path(destination) if destination else default_path(data, layout)
    target.parent.mkdir(parents=True, exist_ok=True)

    if layout == A4:
        largura, altura = A4_SIZE
        margem = 20 * mm
    else:
        largura = 80 * mm
        altura = (128 + 6 * len(_lines(data))) * mm
        margem = 6 * mm

    pdf = canvas.Canvas(str(target), pagesize=(largura, altura))
    pdf.setTitle(f"Comprovante {data.codigo}")
    pdf.setAuthor(data.empresa)

    corpo = 10.5 if layout == A4 else 8
    passo = (7 if layout == A4 else 5) * mm

    y = draw_header(
        pdf,
        company_service.profile(),
        "COMPROVANTE DE PAGAMENTO",
        largura=largura,
        margem=margem,
        topo=altura - margem,
        compacto=layout != A4,
    )

    for rotulo, valor in _lines(data):
        pdf.setFont("Helvetica", corpo)
        pdf.drawString(margem, y, f"{rotulo}:")
        destaque = rotulo in ("Valor recebido", "Situação")
        pdf.setFont("Helvetica-Bold" if destaque else "Helvetica", corpo)
        if layout == A4:
            pdf.drawString(margem + 45 * mm, y, str(valor))
        else:
            pdf.drawRightString(largura - margem, y, str(valor)[:26])
        y -= passo

    y -= passo * 0.4
    pdf.line(margem, y, largura - margem, y)
    y -= passo * 1.6

    pdf.setFont("Helvetica", corpo - 1.5)
    pdf.drawString(margem, y, "Documento gerado pelo sistema. Guarde este comprovante.")
    y -= passo * 2.4

    pdf.line(margem, y, min(largura - margem, margem + 70 * mm), y)
    y -= passo * 0.7
    pdf.setFont("Helvetica", corpo - 1.5)
    pdf.drawString(margem, y, "Assinatura / identificação da empresa")

    pdf.showPage()
    pdf.save()
    return target


def issue(
    payment_id: int,
    destination: Path | str | None = None,
    layout: str = A4,
    actor: SessionUser | None = None,
) -> tuple[Path, ReceiptData]:
    """Emite o comprovante: gera o PDF e registra a emissão na auditoria."""
    if actor:
        require(actor.role, Permission.RECEIPT_ISSUE)
    data = build_receipt(payment_id)
    caminho = render_pdf(data, destination, layout)

    with session_scope() as session:
        log_service.record(
            session,
            LogAction.RECEIPT_ISSUED,
            actor,
            detalhes=f"{data.cliente} — parcela {data.parcela} — {data.codigo} ({layout})",
            parcela_id=None,
            crediario_id=data.crediario_id,
        )
    return caminho, data
