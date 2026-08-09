"""Cabeçalho comum dos documentos impressos (logotipo + identificação).

Um único desenho para comprovante, carnê e documento de cobrança, para que os
três saiam com a mesma identidade visual da Ótica Visão.
"""

from __future__ import annotations

from app.services.company_service import CompanyProfile


def draw_header(
    pdf,  # noqa: ANN001 - canvas do reportlab
    profile: CompanyProfile,
    titulo: str,
    subtitulo: str = "",
    *,
    largura: float,
    margem: float,
    topo: float,
    compacto: bool = False,
) -> float:
    """Desenha o topo do documento e devolve a altura livre restante (y).

    O logotipo entra à esquerda quando cadastrado, e o nome da empresa se
    reposiciona ao lado dele. Sem logotipo, o nome ocupa o canto.
    """
    from reportlab.lib.units import mm

    y = topo
    escala = 0.75 if compacto else 1.0
    logo_lado = (18 if compacto else 22) * mm
    texto_x = margem

    if profile.tem_logo:
        try:
            pdf.drawImage(
                str(profile.logo),
                margem,
                y - logo_lado + 4 * mm,
                width=logo_lado,
                height=logo_lado,
                preserveAspectRatio=True,
                anchor="nw",
                mask="auto",
            )
            texto_x = margem + logo_lado + 4 * mm
        except Exception:  # noqa: BLE001 - imagem inválida não impede a impressão
            texto_x = margem

    pdf.setFont("Helvetica-Bold", 16 * escala)
    pdf.drawString(texto_x, y, profile.titulo[:42])
    y -= 6 * mm * escala

    pdf.setFont("Helvetica", 7.5 * escala)
    for linha in profile.linhas_identificacao():
        pdf.drawString(texto_x, y, linha[:78])
        y -= 3.6 * mm * escala

    y -= 2 * mm
    pdf.setFont("Helvetica-Bold", 13 * escala)
    pdf.drawString(margem, y, titulo)
    y -= 5 * mm * escala

    if subtitulo:
        pdf.setFont("Helvetica-Bold", 9.5 * escala)
        pdf.drawString(margem, y, subtitulo)
        y -= 4.5 * mm * escala

    y -= 1 * mm
    pdf.setLineWidth(1)
    pdf.line(margem, y, largura - margem, y)
    return y - 6 * mm
