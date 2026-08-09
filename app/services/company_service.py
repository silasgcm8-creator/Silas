"""Identidade da loja nos documentos impressos.

Por decisão do proprietário, os documentos usam **apenas o nome ÓTICA VISÃO**:
não existe cadastro de razão social, CNPJ, endereço ou telefone da empresa.
A única coisa configurável é o logotipo, que é opcional e aparece no topo.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from app.config import COMPANY_DEFAULT, settings
from app.database.connection import session_scope
from app.models.log import LogAction
from app.models.setting import Setting
from app.security.authentication import SessionUser
from app.security.permissions import Permission, require
from app.services import log_service
from app.services.errors import BusinessError

KEY_LOGO = "empresa.logotipo"

#: Formatos aceitos para o logotipo — o que o reportlab desenha com segurança.
LOGO_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif")
LOGO_MAX_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class CompanyProfile:
    """Identidade impressa: o nome fixo da loja e, se houver, o logotipo."""

    logo: Path | None = None

    @property
    def titulo(self) -> str:
        """Nome em destaque no topo do documento."""
        return COMPANY_DEFAULT.upper()

    @property
    def nome(self) -> str:
        """Nome como se escreve no meio de uma frase."""
        return COMPANY_DEFAULT

    @property
    def tem_logo(self) -> bool:
        return self.logo is not None and self.logo.is_file()

    def linhas_identificacao(self) -> list[str]:
        """Sem dados cadastrais da empresa, por decisão do proprietário."""
        return []


def _read(session, key: str, default: str = "") -> str:  # noqa: ANN001
    row = session.get(Setting, key)
    return (row.valor if row else "") or default


def profile() -> CompanyProfile:
    """Identidade atual: nome fixo da loja e o logotipo, se cadastrado."""
    with session_scope() as session:
        logo = _read(session, KEY_LOGO)

    caminho = Path(logo) if logo else None
    if caminho is not None and not caminho.is_file():
        caminho = None  # logotipo apagado da pasta não quebra a impressão
    return CompanyProfile(logo=caminho)


def save_logo(source: Path | str, actor: SessionUser | None = None) -> Path:
    """Copia o logotipo para a pasta de dados e registra o caminho.

    A imagem é copiada, e não referenciada no lugar de origem: assim o
    documento continua saindo com a marca mesmo que o arquivo original seja
    movido ou o pen drive retirado.
    """
    if actor:
        require(actor.role, Permission.SETTINGS)

    origem = Path(source).expanduser()
    if not origem.is_file():
        raise BusinessError("Arquivo de logotipo não encontrado.")
    if origem.suffix.lower() not in LOGO_SUFFIXES:
        aceitos = ", ".join(LOGO_SUFFIXES)
        raise BusinessError(f"Formato de imagem não aceito. Use: {aceitos}.")
    if origem.stat().st_size > LOGO_MAX_BYTES:
        raise BusinessError("Logotipo muito grande. Use uma imagem de até 4 MB.")

    destino = settings.data_dir / f"logotipo{origem.suffix.lower()}"
    destino.parent.mkdir(parents=True, exist_ok=True)
    # Remove versões anteriores em outro formato, para não sobrar arquivo órfão.
    for suffix in LOGO_SUFFIXES:
        antigo = settings.data_dir / f"logotipo{suffix}"
        if antigo != destino and antigo.exists():
            antigo.unlink()
    shutil.copy2(origem, destino)

    with session_scope() as session:
        row = session.get(Setting, KEY_LOGO)
        if row is None:
            session.add(Setting(chave=KEY_LOGO, valor=str(destino)))
        else:
            row.valor = str(destino)
        log_service.record(
            session, LogAction.COMPANY_UPDATED, actor, detalhes=f"logotipo: {destino.name}"
        )
    return destino


def remove_logo(actor: SessionUser | None = None) -> None:
    """Retira o logotipo dos documentos (o arquivo copiado é apagado)."""
    if actor:
        require(actor.role, Permission.SETTINGS)
    atual = profile().logo
    with session_scope() as session:
        row = session.get(Setting, KEY_LOGO)
        if row is not None:
            row.valor = ""
        log_service.record(
            session, LogAction.COMPANY_UPDATED, actor, detalhes="logotipo removido"
        )
    if atual is not None and atual.is_file():
        atual.unlink()
