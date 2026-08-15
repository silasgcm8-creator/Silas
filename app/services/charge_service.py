"""Documentos de cobrança: emissão, impressão, histórico e cancelamento.

Um documento é sempre de **uma parcela**. Três modalidades:

- ``LOJA`` — pagamento presencial na Ótica Visão. Nenhum dado bancário sai
  impresso.
- ``BANCO_PIX`` — traz os dados de recebimento de uma conta cadastrada pelo
  administrador. O sistema não inventa nada: imprime só o que foi cadastrado.
- ``BOLETO_REGISTRADO`` — exige integração oficial com a instituição
  financeira. Sem integração, a emissão é recusada com mensagem clara.

A situação do documento acompanha a parcela (EM ABERTO / PAGO / ATRASADO),
exceto quando ele é cancelado.
"""

from __future__ import annotations

import re
import secrets
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.config import APP_NAME, APP_VERSION, settings
from app.database.connection import session_scope
from app.models.bank_account import BankAccount
from app.models.charge import (
    CHARGE_TYPE_LABELS,
    CHARGE_TYPES,
    EVENT_CANCELLED,
    EVENT_CREATED,
    EVENT_PRINTED,
    EVENT_REPRINTED,
    STATUS_CANCELLED,
    STATUS_LATE,
    STATUS_OPEN,
    STATUS_PAID,
    TYPE_BANK,
    TYPE_REGISTERED,
    TYPE_STORE,
    ChargeDocument,
    ChargeEvent,
)
from app.models.client import Client
from app.models.credit import Credit
from app.models.installment import Installment
from app.models.log import LogAction
from app.models.setting import Setting
from app.security.authentication import SessionUser
from app.security.permissions import Permission, require
from app.services import company_service, credit_service, log_service
from app.services.banking import IntegrationNotConfigured, provider_for
from app.services.document_header import draw_header
from app.services.errors import BusinessError, NotFoundError
from app.services.receipt_service import mask_cpf
from app.utils.dates import format_br
from app.utils.money import ZERO, format_brl, to_decimal
from app.utils.validators import ValidationError

TITLE = "DOCUMENTO DE COBRANÇA"
SUBTITLE_STORE = "PAGAMENTO EXCLUSIVO NA LOJA"

#: Prefixo do QR interno. Carrega só o número do documento — nenhum dado pessoal.
QR_PREFIX = "OTICAVISAO:COB"

NUMBER_PREFIX = "OV"

INSTRUCTION = "Apresente este documento no caixa no momento do pagamento."


def store_notice(company: str) -> str:
    return f"Este documento deverá ser pago diretamente na {company}."


def qr_disclaimer(company: str) -> str:
    return (
        "Este QR Code serve exclusivamente para localizar a cobrança dentro do "
        f"sistema da {company}. Não é PIX e não é boleto bancário."
    )


@dataclass(frozen=True)
class PaymentDetails:
    """Dados de recebimento impressos na modalidade Banco / PIX."""

    conta: str = ""
    banco: str = ""
    agencia: str = ""
    numero_conta: str = ""
    beneficiario: str = ""
    documento: str = ""
    pix_chave: str = ""
    pix_tipo: str = ""

    def linhas(self) -> list[tuple[str, str]]:
        """Só os campos preenchidos — nada de rótulo vazio no documento."""
        candidatos = (
            ("Banco", self.banco),
            ("Agência", self.agencia),
            ("Conta", self.numero_conta),
            ("Beneficiário", self.beneficiario),
            ("CPF/CNPJ", self.documento),
        )
        return [(rotulo, valor) for rotulo, valor in candidatos if valor]


@dataclass(frozen=True)
class ChargeView:
    """Tudo que sai impresso no documento de cobrança."""

    id: int
    numero: str
    tipo: str
    cliente: str
    cpf_mascarado: str
    telefone: str
    crediario_id: int
    parcela_numero: int
    parcela_total: int
    parcela_id: int
    emissao: date
    vencimento: date
    valor_original: Decimal
    juros: Decimal
    desconto: Decimal
    valor_atualizado: Decimal
    descricao: str
    observacao: str
    situacao: str
    dias_atraso: int
    pagamento: PaymentDetails
    criado_por: str

    @property
    def parcela(self) -> str:
        return f"{self.parcela_numero:02d}/{self.parcela_total:02d}"

    @property
    def tipo_label(self) -> str:
        return CHARGE_TYPE_LABELS.get(self.tipo, self.tipo)

    @property
    def qr_content(self) -> str:
        return f"{QR_PREFIX}:{self.numero}"

    @property
    def tem_ajuste(self) -> bool:
        return self.juros > ZERO or self.desconto > ZERO

    def file_name(self) -> str:
        """Cobranca_NomeCliente_Parcela_XX_DD-MM-AAAA.pdf (nome seguro)."""
        return (
            f"Cobranca_{sanitize_filename(self.cliente)}_"
            f"Parcela_{self.parcela_numero:02d}_{self.vencimento:%d-%m-%Y}.pdf"
        )


#: Caracteres proibidos em nome de arquivo no Windows.
_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_filename(value: str, limit: int = 40) -> str:
    """Deixa o texto seguro para nome de arquivo no Windows.

    Remove acentos e caracteres proibidos, corta ponto/espaço no fim (que o
    Windows recusa) e desvia de nomes reservados como CON e PRN.
    """
    texto = unicodedata.normalize("NFKD", value or "")
    texto = texto.encode("ascii", "ignore").decode("ascii")
    texto = _INVALID_FILENAME.sub("", texto)
    texto = "_".join(texto.split())[:limit].strip("._")
    if not texto:
        return "Cliente"
    if texto.upper() in _RESERVED_NAMES:
        return f"{texto}_"
    return texto


# ---- configuração das modalidades -----------------------------------

KEY_ALLOWED = "cobranca.formas_permitidas"
KEY_DEFAULT = "cobranca.forma_padrao"
ASK_ALWAYS = "PERGUNTAR"


def allowed_types() -> list[str]:
    """Modalidades liberadas pelo administrador."""
    with session_scope() as session:
        row = session.get(Setting, KEY_ALLOWED)
        bruto = (row.valor if row else "") or ""
    escolhidas = [t for t in bruto.split(",") if t in CHARGE_TYPES]
    # Padrão: loja e banco liberados; registrado depende de integração oficial.
    return escolhidas or [TYPE_STORE, TYPE_BANK]


def default_type() -> str:
    """Modalidade pré-selecionada na tela, ou PERGUNTAR."""
    with session_scope() as session:
        row = session.get(Setting, KEY_DEFAULT)
        valor = (row.valor if row else "") or ASK_ALWAYS
    return valor if valor in (*CHARGE_TYPES, ASK_ALWAYS) else ASK_ALWAYS


def save_charge_settings(
    permitidas: list[str], padrao: str, actor: SessionUser | None = None
) -> tuple[list[str], str]:
    """Grava as modalidades permitidas e a padrão (só administrador)."""
    if actor:
        require(actor.role, Permission.SETTINGS)

    escolhidas = [t for t in permitidas if t in CHARGE_TYPES]
    if not escolhidas:
        raise BusinessError("Deixe pelo menos uma forma de cobrança permitida.")
    if padrao not in (*escolhidas, ASK_ALWAYS):
        raise BusinessError("A forma padrão precisa estar entre as permitidas.")

    with session_scope() as session:
        for chave, valor in ((KEY_ALLOWED, ",".join(escolhidas)), (KEY_DEFAULT, padrao)):
            row = session.get(Setting, chave)
            if row is None:
                session.add(Setting(chave=chave, valor=valor))
            else:
                row.valor = valor
    return escolhidas, padrao


# ---- emissão ---------------------------------------------------------


def _next_number(session) -> str:  # noqa: ANN001
    """Próximo número da sequência: OV-000007.

    A sequência vem do **maior número já emitido**, não da contagem de linhas:
    contar daria o mesmo número duas vezes se um documento fosse removido do
    banco. Se ainda assim houver colisão (duas origens emitindo no mesmo
    instante), completa com um sufixo aleatório em vez de recusar a emissão —
    o mesmo que o código do recebimento faz.
    """
    ultimo = session.scalar(
        sa.select(sa.func.max(ChargeDocument.numero)).where(
            ChargeDocument.numero.like(f"{NUMBER_PREFIX}-%")
        )
    )
    sequencia = 0
    if ultimo:
        sufixo = str(ultimo).rsplit("-", 1)[-1]
        if sufixo.isdigit():
            sequencia = int(sufixo)

    candidato = f"{NUMBER_PREFIX}-{sequencia + 1:06d}"
    existe = session.scalar(
        sa.select(ChargeDocument.id).where(ChargeDocument.numero == candidato)
    )
    if existe is None:
        return candidato
    return f"{NUMBER_PREFIX}-{secrets.token_hex(3).upper()}"


def _record_event(
    session,  # noqa: ANN001
    document_id: int,
    evento: str,
    detalhes: str = "",
    actor: SessionUser | None = None,
) -> None:
    session.add(
        ChargeEvent(
            documento_id=document_id,
            evento=evento,
            detalhes=detalhes[:300],
            usuario_nome=actor.nome if actor else "sistema",
        )
    )


def create(
    installment_id: int,
    tipo: str = TYPE_STORE,
    conta_id: int | None = None,
    juros: object = 0,
    desconto: object = 0,
    descricao: str = "",
    observacao: str = "",
    actor: SessionUser | None = None,
) -> int:
    """Cria o documento de cobrança de uma parcela. Devolve o id."""
    if actor:
        require(actor.role, Permission.CHARGE_ISSUE)

    if tipo not in CHARGE_TYPES:
        raise BusinessError(f"Modalidade de cobrança inválida: {tipo!r}.")
    if tipo not in allowed_types():
        raise BusinessError(
            f"A modalidade '{CHARGE_TYPE_LABELS[tipo]}' não está liberada. "
            "O administrador define isso em Configurações → Cobranças."
        )
    if tipo == TYPE_REGISTERED:
        # Recusa explícita: sem API oficial, não existe título registrado.
        provider_for("boleto").exigir_disponivel()
    if tipo == TYPE_BANK and conta_id is None:
        raise BusinessError("Escolha a conta para recebimento.")

    valor_juros = to_decimal(juros)
    valor_desconto = to_decimal(desconto)
    if valor_juros < ZERO or valor_desconto < ZERO:
        raise ValidationError("Juros e desconto não podem ser negativos.")

    detail, item = credit_service.find_installment(installment_id)
    if item.pago:
        raise BusinessError(
            "Esta parcela já está paga — não é preciso emitir cobrança para ela."
        )

    atualizado = item.valor + valor_juros - valor_desconto
    if atualizado <= ZERO:
        raise ValidationError("O desconto não pode zerar nem inverter o valor a pagar.")

    with session_scope() as session:
        if conta_id is not None:
            conta = session.get(BankAccount, conta_id)
            if conta is None or not conta.ativa:
                raise BusinessError("Conta de recebimento indisponível.")

        ativo = session.scalar(
            sa.select(ChargeDocument).where(
                ChargeDocument.parcela_id == installment_id,
                ChargeDocument.cancelado_em.is_(None),
            )
        )
        if ativo is not None:
            raise BusinessError(
                f"A parcela {item.rotulo} já possui a cobrança {ativo.numero}. "
                "Use Reimprimir, ou cancele a atual antes de emitir outra."
            )

        documento = ChargeDocument(
            numero=_next_number(session),
            tipo=tipo,
            cliente_id=detail.cliente_id,
            crediario_id=detail.id,
            parcela_id=installment_id,
            emissao=date.today(),
            vencimento=item.vencimento,
            valor_original=item.valor,
            juros=valor_juros,
            desconto=valor_desconto,
            valor_atualizado=atualizado,
            descricao=(descricao or detail.descricao or "")[:160],
            observacao=(observacao or "")[:300],
            conta_id=conta_id if tipo == TYPE_BANK else None,
            criado_por_id=actor.id if actor else None,
            criado_por_nome=actor.nome if actor else "sistema",
        )
        try:
            session.add(documento)
            session.flush()
        except IntegrityError as exc:
            # Rede de segurança do banco: o índice único parcial de `parcela_id`
            # barra uma segunda cobrança ativa mesmo que a conferência acima
            # tenha passado — duas origens emitindo no mesmo instante. Sem isto,
            # o funcionário veria um erro cru do banco em vez de um aviso.
            raise BusinessError(
                f"A parcela {item.rotulo} acabou de receber uma cobrança por "
                "outro caminho. Atualize a tela e use Reimprimir."
            ) from exc

        _record_event(
            session,
            documento.id,
            EVENT_CREATED,
            f"{CHARGE_TYPE_LABELS[tipo]} — {format_brl(atualizado)}",
            actor,
        )
        log_service.record(
            session,
            LogAction.CHARGE_ISSUED,
            actor,
            detalhes=(
                f"{detail.cliente} — parcela {item.rotulo} — {documento.numero} "
                f"({CHARGE_TYPE_LABELS[tipo]}) — {format_brl(atualizado)}"
            ),
            cliente_id=detail.cliente_id,
            crediario_id=detail.id,
            parcela_id=installment_id,
        )
        return documento.id


def build(document_id: int) -> ChargeView:
    """Monta a visão completa do documento para tela e impressão."""
    with session_scope() as session:
        documento = session.get(ChargeDocument, document_id)
        if documento is None:
            raise NotFoundError("Documento de cobrança não encontrado.")

        row = session.execute(
            sa.select(
                Client.nome,
                Client.cpf,
                Client.telefone,
                Installment.numero,
                Installment.pago,
                Credit.parcelas,
            )
            .select_from(ChargeDocument)
            .join(Client, Client.id == ChargeDocument.cliente_id)
            .join(Installment, Installment.id == ChargeDocument.parcela_id)
            .join(Credit, Credit.id == ChargeDocument.crediario_id)
            .where(ChargeDocument.id == document_id)
        ).first()
        if row is None:  # pragma: no cover - integridade garante o vínculo
            raise NotFoundError("Documento de cobrança incompleto.")

        conta = documento.conta
        pagamento = PaymentDetails()
        if documento.tipo == TYPE_BANK and conta is not None:
            pagamento = PaymentDetails(
                conta=conta.identificacao,
                banco=conta.banco_completo,
                agencia=conta.agencia_completa,
                numero_conta=(
                    f"{conta.conta_completa} ({conta.tipo_conta})"
                    if conta.tipo_conta and conta.conta_completa
                    else conta.conta_completa
                ),
                beneficiario=conta.beneficiario_nome,
                documento=conta.beneficiario_documento,
                pix_chave=conta.pix_chave,
                pix_tipo=conta.pix_tipo,
            )

        situacao = documento.status(bool(row.pago))
        atraso = (date.today() - documento.vencimento).days if situacao == STATUS_LATE else 0

        return ChargeView(
            id=documento.id,
            numero=documento.numero,
            tipo=documento.tipo,
            cliente=row.nome,
            cpf_mascarado=mask_cpf(row.cpf),
            telefone=row.telefone,
            crediario_id=documento.crediario_id,
            parcela_numero=row.numero,
            parcela_total=row.parcelas,
            parcela_id=documento.parcela_id,
            emissao=documento.emissao,
            vencimento=documento.vencimento,
            valor_original=documento.valor_original,
            juros=documento.juros,
            desconto=documento.desconto,
            valor_atualizado=documento.valor_atualizado,
            descricao=documento.descricao,
            observacao=documento.observacao,
            situacao=situacao,
            dias_atraso=atraso,
            pagamento=pagamento,
            criado_por=documento.criado_por_nome,
        )


def find_by_number(numero: str) -> ChargeView | None:
    """Localiza pelo número do documento ou pelo conteúdo do QR interno."""
    texto = (numero or "").strip().upper()
    if texto.startswith(QR_PREFIX):
        texto = texto[len(QR_PREFIX) :].lstrip(":/")
    if not texto:
        return None
    with session_scope() as session:
        documento = session.scalar(
            sa.select(ChargeDocument).where(ChargeDocument.numero == texto)
        )
        document_id = documento.id if documento else None
    return build(document_id) if document_id else None


def active_for_installment(installment_id: int) -> ChargeView | None:
    """Documento ativo da parcela, se já houver um."""
    with session_scope() as session:
        documento = session.scalar(
            sa.select(ChargeDocument).where(
                ChargeDocument.parcela_id == installment_id,
                ChargeDocument.cancelado_em.is_(None),
            )
        )
        document_id = documento.id if documento else None
    return build(document_id) if document_id else None


def cancel(document_id: int, motivo: str, actor: SessionUser | None = None) -> None:
    """Cancela o documento. O registro permanece, com autor e motivo."""
    if actor:
        require(actor.role, Permission.CHARGE_CANCEL)
    motivo = " ".join((motivo or "").split())
    if len(motivo) < 5:
        raise ValidationError(
            "Informe o motivo do cancelamento (no mínimo 5 caracteres)."
        )

    with session_scope() as session:
        documento = session.get(ChargeDocument, document_id)
        if documento is None:
            raise NotFoundError("Documento de cobrança não encontrado.")
        if documento.cancelado:
            raise BusinessError("Este documento já está cancelado.")

        parcela = session.get(Installment, documento.parcela_id)
        if parcela is not None and parcela.pago:
            raise BusinessError(
                "A parcela já foi paga. Para desfazer, use o estorno do pagamento."
            )

        documento.cancelado_em = datetime.now()
        documento.cancelado_por = actor.nome if actor else "sistema"
        documento.motivo_cancelamento = motivo[:300]

        _record_event(session, document_id, EVENT_CANCELLED, motivo, actor)
        log_service.record(
            session,
            LogAction.CHARGE_CANCELLED,
            actor,
            detalhes=f"{documento.numero} — motivo: {motivo}",
            cliente_id=documento.cliente_id,
            crediario_id=documento.crediario_id,
            parcela_id=documento.parcela_id,
        )


# ---- listagem e filtros ---------------------------------------------


@dataclass(frozen=True)
class ChargeRow:
    """Linha da tela BOLETOS."""

    id: int
    numero: str
    cliente: str
    cpf: str
    crediario_id: int
    parcela: str
    emissao: date
    vencimento: date
    valor: Decimal
    tipo: str
    tipo_label: str
    conta: str
    situacao: str

    @property
    def cancelado(self) -> bool:
        return self.situacao == STATUS_CANCELLED


def list_documents(
    term: str = "",
    situacao: str = "",
    tipo: str = "",
    conta_id: int | None = None,
    inicio: date | None = None,
    fim: date | None = None,
    por_vencimento: bool = False,
    limit: int = 500,
    actor: SessionUser | None = None,
) -> list[ChargeRow]:
    """Documentos filtrados para a tela BOLETOS.

    `por_vencimento` troca o intervalo de datas de emissão para vencimento.

    Sem a visão financeira, um documento vencido aparece como ``EM ABERTO``: a
    lista serve para localizar e reimprimir o documento de um cliente, não para
    varrer quem está atrasado. Pelo mesmo motivo, filtrar por ``ATRASADO`` não
    devolve nada para esse perfil, em vez de virar uma lista de inadimplentes.
    """
    hoje = date.today()
    atrasos = actor is None or actor.can(Permission.FINANCE_OVERVIEW)
    if not atrasos and situacao == STATUS_LATE:
        return []
    with session_scope() as session:
        stmt = (
            sa.select(
                ChargeDocument.id,
                ChargeDocument.numero,
                Client.nome,
                Client.cpf,
                ChargeDocument.crediario_id,
                Installment.numero.label("parcela_numero"),
                Installment.pago,
                Credit.parcelas,
                ChargeDocument.emissao,
                ChargeDocument.vencimento,
                ChargeDocument.valor_atualizado,
                ChargeDocument.tipo,
                ChargeDocument.cancelado_em,
                BankAccount.identificacao.label("conta"),
            )
            .select_from(ChargeDocument)
            .join(Client, Client.id == ChargeDocument.cliente_id)
            .join(Installment, Installment.id == ChargeDocument.parcela_id)
            .join(Credit, Credit.id == ChargeDocument.crediario_id)
            .outerjoin(BankAccount, BankAccount.id == ChargeDocument.conta_id)
            .order_by(ChargeDocument.id.desc())
            .limit(limit)
        )

        termo = (term or "").strip()
        if termo:
            like = f"%{termo}%"
            filtros = [
                Client.nome.ilike(like),
                Client.cpf.like(like),
                ChargeDocument.numero.ilike(like),
            ]
            if termo.isdigit():
                filtros.append(ChargeDocument.crediario_id == int(termo))
                filtros.append(Installment.numero == int(termo))
            stmt = stmt.where(sa.or_(*filtros))

        if tipo:
            stmt = stmt.where(ChargeDocument.tipo == tipo)
        if conta_id is not None:
            stmt = stmt.where(ChargeDocument.conta_id == conta_id)

        campo = ChargeDocument.vencimento if por_vencimento else ChargeDocument.emissao
        if inicio is not None:
            stmt = stmt.where(campo >= inicio)
        if fim is not None:
            stmt = stmt.where(campo <= fim)

        ativo = ChargeDocument.cancelado_em.is_(None)
        if situacao == STATUS_CANCELLED:
            stmt = stmt.where(ChargeDocument.cancelado_em.is_not(None))
        elif situacao == STATUS_PAID:
            stmt = stmt.where(ativo, Installment.pago.is_(True))
        elif situacao == STATUS_LATE:
            stmt = stmt.where(
                ativo, Installment.pago.is_(False), ChargeDocument.vencimento < hoje
            )
        elif situacao == STATUS_OPEN:
            stmt = stmt.where(
                ativo, Installment.pago.is_(False), ChargeDocument.vencimento >= hoje
            )

        linhas = []
        for row in session.execute(stmt).all():
            if row.cancelado_em is not None:
                estado = STATUS_CANCELLED
            elif row.pago:
                estado = STATUS_PAID
            elif row.vencimento < hoje and atrasos:
                estado = STATUS_LATE
            else:
                estado = STATUS_OPEN
            linhas.append(
                ChargeRow(
                    id=row.id,
                    numero=row.numero,
                    cliente=row.nome,
                    cpf=row.cpf,
                    crediario_id=row.crediario_id,
                    parcela=f"{row.parcela_numero:02d}/{row.parcelas:02d}",
                    emissao=row.emissao,
                    vencimento=row.vencimento,
                    valor=row.valor_atualizado,
                    tipo=row.tipo,
                    tipo_label=CHARGE_TYPE_LABELS.get(row.tipo, row.tipo),
                    conta=row.conta or "",
                    situacao=estado,
                )
            )
        return linhas


@dataclass(frozen=True)
class IssuableRow:
    """Parcela em aberto de **um** cliente, pronta para receber cobrança.

    O contrato é deliberadamente estreito: o que a operação exige para escolher
    a parcela e imprimir. Sem situação de atraso, sem dias em atraso, sem saldo
    do cliente — o funcionário emite um documento, não consulta inadimplência.
    """

    parcela_id: int
    crediario_id: int
    parcela: str
    vencimento: date
    valor: Decimal
    #: Número da cobrança ativa que já existe para esta parcela, se houver.
    documento: str | None
    documento_id: int | None

    @property
    def ja_tem_documento(self) -> bool:
        return self.documento_id is not None


def issuable_for_client(client_id: int, actor: SessionUser) -> list[IssuableRow]:
    """Parcelas em aberto do cliente, em uma consulta só.

    Usada pela tela GERAR BOLETO. Exige a permissão de emitir cobrança e nunca
    olha para fora do cliente informado.
    """
    require(actor.role, Permission.CHARGE_ISSUE)
    with session_scope() as session:
        ativo = ChargeDocument.cancelado_em.is_(None)
        stmt = (
            sa.select(
                Installment.id,
                Installment.numero,
                Installment.vencimento,
                Installment.valor,
                Credit.id.label("crediario_id"),
                Credit.parcelas,
                ChargeDocument.id.label("documento_id"),
                ChargeDocument.numero.label("documento"),
            )
            .select_from(Installment)
            .join(Credit, Credit.id == Installment.crediario_id)
            .outerjoin(
                ChargeDocument,
                sa.and_(ChargeDocument.parcela_id == Installment.id, ativo),
            )
            .where(Credit.cliente_id == client_id, Installment.pago.is_(False))
            .order_by(Installment.vencimento, Installment.id)
        )
        return [
            IssuableRow(
                parcela_id=row.id,
                crediario_id=row.crediario_id,
                parcela=f"{row.numero:02d}/{row.parcelas:02d}",
                vencimento=row.vencimento,
                valor=row.valor,
                documento=row.documento,
                documento_id=row.documento_id,
            )
            for row in session.execute(stmt).all()
        ]


@dataclass(frozen=True)
class EventRow:
    evento: str
    detalhes: str
    usuario: str
    quando: datetime


def history(document_id: int) -> list[EventRow]:
    """Eventos do documento, do mais recente para o mais antigo."""
    with session_scope() as session:
        stmt = (
            sa.select(ChargeEvent)
            .where(ChargeEvent.documento_id == document_id)
            .order_by(ChargeEvent.criado_em.desc(), ChargeEvent.id.desc())
        )
        return [
            EventRow(
                evento=item.evento,
                detalhes=item.detalhes,
                usuario=item.usuario_nome,
                quando=item.criado_em,
            )
            for item in session.scalars(stmt).all()
        ]


# ---- PDF -------------------------------------------------------------


def default_path(view: ChargeView) -> Path:
    pasta = settings.receipt_dir
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / view.file_name()


def render_pdf(view: ChargeView, destination: Path | str | None = None) -> Path:
    """Desenha o documento em A4, com comprovante destacável no rodapé."""
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
    target = Path(destination) if destination else default_path(view)
    target.parent.mkdir(parents=True, exist_ok=True)

    largura, altura = A4
    margem = 18 * mm
    pdf = canvas.Canvas(str(target), pagesize=A4)
    pdf.setTitle(f"Cobrança {view.numero}")
    pdf.setAuthor(company.titulo)

    y = draw_header(
        pdf,
        company,
        TITLE,
        SUBTITLE_STORE if view.tipo == TYPE_STORE else "",
        largura=largura,
        margem=margem,
        topo=altura - margem,
    )

    # ---- paleta e caixas --------------------------------------------
    # Grafite em vez de preto puro e um cinza claro de fundo: o documento sai
    # da impressora com a mesma leitura de um extrato de banco, sem parecer
    # uma folha de máquina de escrever.
    TINTA = colors.HexColor("#1F2937")
    SUAVE = colors.HexColor("#6B7280")
    LINHA = colors.HexColor("#D1D5DB")
    FUNDO = colors.HexColor("#F3F4F6")
    DESTAQUE = colors.HexColor("#312E81")
    ALERTA = colors.HexColor("#B00020")
    util = largura - 2 * margem

    def caixa(topo: float, alta: float, titulo: str = "") -> float:
        """Moldura com faixa de título. Devolve o y do primeiro conteúdo."""
        pdf.setFillColor(colors.white)
        pdf.setStrokeColor(LINHA)
        pdf.setLineWidth(0.8)
        pdf.rect(margem, topo - alta, util, alta, stroke=1, fill=1)
        if titulo:
            faixa = 7 * mm
            pdf.setFillColor(FUNDO)
            pdf.rect(margem, topo - faixa, util, faixa, stroke=0, fill=1)
            pdf.setStrokeColor(LINHA)
            pdf.line(margem, topo - faixa, margem + util, topo - faixa)
            pdf.setFillColor(SUAVE)
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(margem + 4 * mm, topo - faixa + 2.4 * mm, titulo.upper())
            pdf.setFillColor(TINTA)
            return topo - faixa - 5.5 * mm
        pdf.setFillColor(TINTA)
        return topo - 5.5 * mm

    def par(x: float, linha_y: float, rotulo: str, valor: str, largura_rotulo: float) -> None:
        pdf.setFillColor(SUAVE)
        pdf.setFont("Helvetica", 8.5)
        pdf.drawString(x, linha_y, rotulo.upper())
        pdf.setFillColor(TINTA)
        pdf.setFont("Helvetica-Bold", 9.5)
        pdf.drawString(x + largura_rotulo, linha_y, str(valor))

    pdf.setFillColor(SUAVE)
    pdf.setFont("Helvetica", 8.5)
    pdf.drawRightString(largura - margem, y, f"Documento {view.numero}")
    pdf.setFillColor(TINTA)
    y -= 6 * mm

    if view.situacao == STATUS_CANCELLED:
        pdf.setFillColor(ALERTA)
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawRightString(largura - margem, y, "DOCUMENTO CANCELADO")
        pdf.setFillColor(TINTA)
        y -= 7 * mm

    # ---- identificação, em duas colunas -----------------------------
    esquerda = [
        ("Cliente", view.cliente[:34]),
        ("CPF", view.cpf_mascarado),
        ("Telefone", view.telefone),
    ]
    direita = [
        ("Crediário", f"{view.crediario_id:06d}"),
        ("Parcela", f"{view.parcela} de {view.parcela_total}"),
        ("Emissão", format_br(view.emissao)),
    ]
    direita.append(("Documento", view.numero))

    # A descrição da compra ganha a linha inteira: numa coluna ela seria
    # cortada no meio da palavra.
    linhas_extra = 1 if view.descricao else 0
    alta = 7 * mm + (len(esquerda) + linhas_extra) * 5.8 * mm + 3 * mm
    linha_y = caixa(y, alta, "Identificação")
    meio_col = margem + util / 2
    for indice in range(len(esquerda)):
        par(margem + 4 * mm, linha_y, *esquerda[indice], 22 * mm)
        if indice < len(direita):
            par(meio_col + 4 * mm, linha_y, *direita[indice], 22 * mm)
        linha_y -= 5.8 * mm
    if view.descricao:
        par(margem + 4 * mm, linha_y, "Compra", view.descricao[:78], 22 * mm)
    y -= alta + 5 * mm

    # ---- valor e vencimento -----------------------------------------
    alta = 27 * mm
    pdf.setFillColor(FUNDO)
    pdf.setStrokeColor(DESTAQUE)
    pdf.setLineWidth(1.2)
    pdf.rect(margem, y - alta, util, alta, stroke=1, fill=1)
    pdf.setFillColor(DESTAQUE)
    pdf.rect(margem, y - alta, 2.2 * mm, alta, stroke=0, fill=1)

    meio = margem + util * 0.52
    pdf.setStrokeColor(LINHA)
    pdf.setLineWidth(0.8)
    pdf.line(meio, y - alta + 4 * mm, meio, y - 4 * mm)

    pdf.setFillColor(SUAVE)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(margem + 8 * mm, y - 8 * mm, "VALOR A PAGAR")
    pdf.setFillColor(DESTAQUE)
    pdf.setFont("Helvetica-Bold", 26)
    pdf.drawString(margem + 8 * mm, y - 19.5 * mm, format_brl(view.valor_atualizado))

    pdf.setFillColor(SUAVE)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(meio + 6 * mm, y - 8 * mm, "VENCIMENTO")
    pdf.setFillColor(TINTA)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(meio + 6 * mm, y - 19.5 * mm, format_br(view.vencimento))

    # A composição fica ao lado do valor, não numa lista solta acima dele:
    # quem confere quer ver de onde veio o número no mesmo golpe de vista.
    if view.tem_ajuste:
        cy_ajuste = y - 24.5 * mm
        pdf.setFillColor(SUAVE)
        pdf.setFont("Helvetica", 7.5)
        partes = [f"parcela {format_brl(view.valor_original)}"]
        if view.juros > ZERO:
            partes.append(f"+ juros/multa {format_brl(view.juros)}")
        if view.desconto > ZERO:
            partes.append(f"- desconto {format_brl(view.desconto)}")
        pdf.drawString(margem + 8 * mm, cy_ajuste, "   ".join(partes))
        pdf.setFillColor(TINTA)
    y -= alta + 4 * mm

    if view.situacao == STATUS_LATE:
        pdf.setFillColor(ALERTA)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(margem, y, f"Parcela em atraso — {view.dias_atraso} dias")
        pdf.setFillColor(TINTA)
        y -= 6 * mm
    y -= 1 * mm

    # ---- como pagar + QR, lado a lado -------------------------------
    qr_lado = 26 * mm
    alta = 44 * mm
    linha_y = caixa(y, alta, "Como pagar")
    largura_texto = util - qr_lado - 14 * mm

    if view.tipo == TYPE_STORE:
        pdf.setFillColor(DESTAQUE)
        pdf.setFont("Helvetica-Bold", 11.5)
        pdf.drawString(margem + 4 * mm, linha_y, f"PAGAMENTO NA {company.titulo}")
        pdf.setFillColor(TINTA)
        linha_y -= 6 * mm
        pdf.setFont("Helvetica", 9)
        for texto in _wrap(store_notice(company.nome), 58):
            pdf.drawString(margem + 4 * mm, linha_y, texto)
            linha_y -= 4.4 * mm
        linha_y -= 1 * mm
        pdf.setFont("Helvetica-Bold", 9.5)
        for texto in _wrap(INSTRUCTION, 56):
            pdf.drawString(margem + 4 * mm, linha_y, texto)
            linha_y -= 4.6 * mm
    else:
        pdf.setFillColor(DESTAQUE)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(margem + 4 * mm, linha_y, "DADOS PARA PAGAMENTO")
        pdf.setFillColor(TINTA)
        linha_y -= 6 * mm
        for rotulo, valor in view.pagamento.linhas():
            par(margem + 4 * mm, linha_y, rotulo, str(valor), 26 * mm)
            linha_y -= 4.9 * mm
        if view.pagamento.pix_chave:
            linha_y -= 1 * mm
            pdf.setFillColor(SUAVE)
            pdf.setFont("Helvetica-Bold", 8)
            rotulo_pix = (
                f"CHAVE PIX ({view.pagamento.pix_tipo})"
                if view.pagamento.pix_tipo
                else "CHAVE PIX"
            )
            pdf.drawString(margem + 4 * mm, linha_y, rotulo_pix)
            pdf.setFillColor(TINTA)
            linha_y -= 4.6 * mm
            pdf.setFont("Courier-Bold", 10.5)
            pdf.drawString(margem + 4 * mm, linha_y, view.pagamento.pix_chave[:48])
            linha_y -= 5 * mm

    if view.observacao:
        pdf.setFillColor(SUAVE)
        pdf.setFont("Helvetica-Oblique", 8.5)
        for texto in _wrap(f"Observação: {view.observacao}", 62)[:2]:
            pdf.drawString(margem + 4 * mm, linha_y, texto)
            linha_y -= 4 * mm
        pdf.setFillColor(TINTA)

    # QR ancorado à direita, dentro da mesma moldura.
    qr_x = largura - margem - qr_lado - 5 * mm
    qr_y = y - alta + 9 * mm
    qr = createBarcodeDrawing("QR", value=view.qr_content, width=qr_lado, height=qr_lado)
    renderPDF.draw(qr, pdf, qr_x, qr_y)
    pdf.setFillColor(SUAVE)
    pdf.setFont("Helvetica", 6.5)
    pdf.drawCentredString(qr_x + qr_lado / 2, qr_y - 4 * mm, "USO INTERNO — NÃO É PIX")
    pdf.setFillColor(TINTA)
    pdf.setFont("Courier-Bold", 8)
    pdf.drawCentredString(qr_x + qr_lado / 2, qr_y - 7.5 * mm, view.numero)
    y -= alta + 4 * mm

    pdf.setFillColor(SUAVE)
    pdf.setFont("Helvetica", 7)
    for texto in _wrap(qr_disclaimer(company.nome), 118):
        pdf.drawString(margem, y, texto)
        y -= 3.4 * mm
    pdf.setFillColor(TINTA)

    # ---- comprovante destacável -------------------------------------
    # O corte acompanha o fim do conteúdo. Fixo, ele deixava um vazio no meio
    # da folha quando o documento era curto — e vazio no meio parece defeito,
    # enquanto sobra no rodapé parece margem.
    corte = max(margem + 52 * mm, y - 8 * mm)
    pdf.setDash(3, 3)
    pdf.setLineWidth(0.8)
    pdf.line(margem, corte, largura - margem, corte)
    pdf.setDash()
    pdf.setFont("Helvetica", 7)
    pdf.drawRightString(largura - margem, corte + 1.5 * mm, "destaque aqui")

    cy = corte - 6 * mm
    pdf.setFillColor(DESTAQUE)
    pdf.setFont("Helvetica-Bold", 10.5)
    pdf.drawString(margem, cy, "COMPROVANTE DE PAGAMENTO")
    pdf.setFillColor(SUAVE)
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(largura - margem, cy, f"{company.titulo} — {view.numero}")
    pdf.setFillColor(TINTA)
    cy -= 2.5 * mm
    pdf.setStrokeColor(LINHA)
    pdf.setLineWidth(0.8)
    pdf.line(margem, cy, largura - margem, cy)
    cy -= 6 * mm

    coluna2 = margem + 92 * mm
    pares = [
        ("Cliente", view.cliente[:30]),
        ("CPF", view.cpf_mascarado),
        ("Documento", view.numero),
        ("Parcela", view.parcela),
        ("Valor", format_brl(view.valor_atualizado)),
        ("Vencimento", format_br(view.vencimento)),
    ]
    for indice, (rotulo, valor) in enumerate(pares):
        x = margem if indice % 2 == 0 else coluna2
        linha_y = cy - (indice // 2) * 5.4 * mm
        par(x, linha_y, rotulo, str(valor), 24 * mm)
    cy -= 3 * 5.4 * mm + 6 * mm

    pdf.setFont("Helvetica", 8.5)
    pdf.drawString(margem, cy, "Data do pagamento: ____/____/________")
    pdf.drawString(coluna2, cy, "Forma de pagamento: ____________________")
    cy -= 13 * mm

    pdf.setLineWidth(0.6)
    pdf.line(margem, cy, margem + 80 * mm, cy)
    pdf.setFont("Helvetica", 7.5)
    pdf.drawString(margem, cy - 4 * mm, "Assinatura / autenticação")

    pdf.setFont("Helvetica", 6.5)
    pdf.drawRightString(
        largura - margem, margem, f"{APP_NAME} {APP_VERSION} — {view.tipo_label}"
    )

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


def issue_pdf(
    document_id: int,
    destination: Path | str | None = None,
    actor: SessionUser | None = None,
) -> tuple[Path, ChargeView]:
    """Gera (ou regera) o PDF e registra impressão/reimpressão no histórico."""
    if actor:
        require(actor.role, Permission.CHARGE_ISSUE)
    view = build(document_id)
    caminho = render_pdf(view, destination)

    with session_scope() as session:
        documento = session.get(ChargeDocument, document_id)
        if documento is None:  # pragma: no cover - build já validou
            raise NotFoundError("Documento de cobrança não encontrado.")
        primeira = documento.impressoes == 0
        documento.impressoes += 1
        documento.pdf_path = str(caminho)
        _record_event(
            session,
            document_id,
            EVENT_PRINTED if primeira else EVENT_REPRINTED,
            caminho.name,
            actor,
        )
        if not primeira:
            log_service.record(
                session,
                LogAction.CHARGE_REPRINTED,
                actor,
                detalhes=f"{documento.numero} ({documento.impressoes}ª via)",
                cliente_id=documento.cliente_id,
                crediario_id=documento.crediario_id,
            )
    return caminho, view


def create_and_issue(
    installment_id: int,
    tipo: str = TYPE_STORE,
    conta_id: int | None = None,
    juros: object = 0,
    desconto: object = 0,
    descricao: str = "",
    observacao: str = "",
    destination: Path | str | None = None,
    actor: SessionUser | None = None,
) -> tuple[int, Path, ChargeView]:
    """Atalho do balcão: cria o documento e já gera o PDF."""
    document_id = create(
        installment_id, tipo, conta_id, juros, desconto, descricao, observacao, actor
    )
    caminho, view = issue_pdf(document_id, destination, actor)
    return document_id, caminho, view


__all__ = [
    "ASK_ALWAYS",
    "ChargeRow",
    "ChargeView",
    "EventRow",
    "IntegrationNotConfigured",
    "IssuableRow",
    "PaymentDetails",
    "TYPE_BANK",
    "TYPE_REGISTERED",
    "TYPE_STORE",
    "active_for_installment",
    "allowed_types",
    "build",
    "cancel",
    "create",
    "create_and_issue",
    "default_type",
    "find_by_number",
    "history",
    "issuable_for_client",
    "issue_pdf",
    "list_documents",
    "render_pdf",
    "sanitize_filename",
    "save_charge_settings",
]
