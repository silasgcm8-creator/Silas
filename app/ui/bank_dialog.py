"""Cadastro de conta de recebimento (janela do administrador)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.bank_account import ACCOUNT_TYPES, PIX_KEY_TYPES
from app.security.permissions import PermissionDenied
from app.services import bank_account_service
from app.services.errors import BusinessError, NotFoundError
from app.ui.context import AppContext
from app.ui.widgets import (
    Card,
    button,
    field_label,
    page_header,
    primary_button,
    warn,
)
from app.utils.cnpj import format_document


class BankAccountDialog(QDialog):
    """Todos os campos vêm digitados pelo administrador — nada é gerado."""

    def __init__(
        self, ctx: AppContext, account_id: int | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.account_id = account_id
        editando = account_id is not None
        self.setWindowTitle("Editar conta" if editando else "Nova conta de recebimento")
        self.setMinimumWidth(620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)
        layout.addWidget(
            page_header(
                "Editar conta" if editando else "Nova conta de recebimento",
                "Preencha apenas o que a loja realmente usa",
            )
        )

        card = Card()
        form = QFormLayout()
        form.setSpacing(9)

        self.fields: dict[str, QLineEdit] = {}
        for chave, rotulo, dica in (
            ("identificacao", "IDENTIFICAÇÃO", "Ex.: Banco Principal, PIX Loja"),
            ("banco_nome", "NOME DO BANCO", "Ex.: Banco do Brasil"),
            ("banco_codigo", "CÓDIGO DO BANCO", "Ex.: 001"),
            ("agencia", "AGÊNCIA", ""),
            ("agencia_digito", "DÍGITO DA AGÊNCIA", ""),
            ("conta", "CONTA", ""),
            ("conta_digito", "DÍGITO DA CONTA", ""),
            ("beneficiario_nome", "BENEFICIÁRIO", "Nome de quem recebe"),
            ("beneficiario_documento", "CPF / CNPJ DO BENEFICIÁRIO", ""),
            ("pix_chave", "CHAVE PIX", ""),
            ("carteira", "CARTEIRA", "Somente para cobrança registrada"),
            ("convenio", "CONVÊNIO", "Somente para cobrança registrada"),
            ("codigo_beneficiario", "CÓDIGO DO BENEFICIÁRIO", "Somente para registrada"),
        ):
            campo = QLineEdit()
            campo.setMinimumHeight(34)
            if dica:
                campo.setPlaceholderText(dica)
            self.fields[chave] = campo
            form.addRow(field_label(rotulo), campo)

        self.fields["beneficiario_documento"].textChanged.connect(self._mask_document)

        self.tipo_conta = QComboBox()
        self.tipo_conta.setMinimumHeight(34)
        self.tipo_conta.addItem("—", "")
        for tipo in ACCOUNT_TYPES:
            self.tipo_conta.addItem(tipo, tipo)
        form.addRow(field_label("TIPO DE CONTA"), self.tipo_conta)

        self.pix_tipo = QComboBox()
        self.pix_tipo.setMinimumHeight(34)
        self.pix_tipo.addItem("—", "")
        for tipo in PIX_KEY_TYPES:
            self.pix_tipo.addItem(tipo, tipo)
        form.addRow(field_label("TIPO DA CHAVE PIX"), self.pix_tipo)

        card.body.addLayout(form)
        layout.addWidget(card)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancelar = button("Cancelar", ghost=True)
        cancelar.clicked.connect(self.reject)
        salvar = primary_button("Salvar conta", "check")
        salvar.clicked.connect(self._save)
        actions.addWidget(cancelar)
        actions.addWidget(salvar)
        layout.addLayout(actions)

        if editando:
            self._load()

    def _mask_document(self, text: str) -> None:
        campo = self.fields["beneficiario_documento"]
        masked = format_document(text)
        if masked != text:
            campo.blockSignals(True)
            campo.setText(masked)
            campo.setCursorPosition(len(masked))
            campo.blockSignals(False)

    def _load(self) -> None:
        try:
            conta = bank_account_service.get_account(self.account_id)  # type: ignore[arg-type]
        except NotFoundError as exc:
            warn(self, "Conta", str(exc))
            self.reject()
            return
        self.fields["identificacao"].setText(conta.identificacao)
        self.fields["beneficiario_nome"].setText(conta.beneficiario)
        self.fields["beneficiario_documento"].setText(conta.documento)
        self.fields["pix_chave"].setText(conta.pix)
        indice = self.pix_tipo.findData(conta.pix_tipo)
        self.pix_tipo.setCurrentIndex(max(0, indice))
        indice = self.tipo_conta.findData(conta.tipo_conta)
        self.tipo_conta.setCurrentIndex(max(0, indice))
        # Banco, agência e conta vêm formatados na listagem; recarrega do modelo.
        from app.database.connection import session_scope
        from app.models.bank_account import BankAccount

        with session_scope() as session:
            registro = session.get(BankAccount, self.account_id)
            if registro is None:
                return
            for chave in (
                "banco_nome", "banco_codigo", "agencia", "agencia_digito",
                "conta", "conta_digito", "carteira", "convenio",
                "codigo_beneficiario",
            ):
                self.fields[chave].setText(getattr(registro, chave) or "")

    def _values(self) -> dict[str, str]:
        dados = {chave: campo.text().strip() for chave, campo in self.fields.items()}
        dados["tipo_conta"] = self.tipo_conta.currentData() or ""
        dados["pix_tipo"] = self.pix_tipo.currentData() or ""
        return dados

    def _save(self) -> None:
        dados = self._values()
        try:
            if self.account_id is None:
                bank_account_service.create_account(actor=self.ctx.user, **dados)
            else:
                bank_account_service.update_account(
                    self.account_id, actor=self.ctx.user, **dados
                )
        except (BusinessError, NotFoundError, PermissionDenied) as exc:
            warn(self, "Conta de recebimento", str(exc))
            return
        self.ctx.notify("Conta de recebimento salva.")
        self.accept()
