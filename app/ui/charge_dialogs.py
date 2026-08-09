"""Janelas do módulo de cobranças: modalidade e recebimento no caixa."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.charge import CHARGE_TYPE_LABELS, TYPE_BANK, TYPE_REGISTERED, TYPE_STORE
from app.models.status import PaymentMethod
from app.security.permissions import PermissionDenied
from app.services import bank_account_service, charge_service
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
from app.utils.money import ZERO, format_brl, parse_brl


class ChargeTypeDialog(QDialog):
    """Escolha da modalidade de cobrança, com os campos certos para cada uma."""

    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.tipo = TYPE_STORE
        self.conta_id: int | None = None
        self.juros: Decimal = ZERO
        self.desconto: Decimal = ZERO
        self.observacao = ""

        self.setWindowTitle("Criar cobrança")
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)
        layout.addWidget(
            page_header("Criar cobrança", "Escolha como o cliente vai pagar")
        )

        card = Card()
        form = QFormLayout()
        form.setSpacing(10)

        self.type_combo = QComboBox()
        self.type_combo.setMinimumHeight(38)
        permitidas = charge_service.allowed_types()
        for tipo in (TYPE_STORE, TYPE_BANK, TYPE_REGISTERED):
            if tipo in permitidas:
                self.type_combo.addItem(CHARGE_TYPE_LABELS[tipo], tipo)
        self.type_combo.currentIndexChanged.connect(lambda *_: self._type_changed())
        form.addRow(field_label("TIPO DE PAGAMENTO"), self.type_combo)

        self.account_label = field_label("CONTA PARA RECEBIMENTO")
        self.account_combo = QComboBox()
        self.account_combo.setMinimumHeight(38)
        self.contas = bank_account_service.list_accounts()
        for conta in self.contas:
            self.account_combo.addItem(conta.resumo, conta.id)
        form.addRow(self.account_label, self.account_combo)

        self.juros_edit = QLineEdit("0,00")
        self.juros_edit.setMinimumHeight(38)
        form.addRow(field_label("JUROS / MULTA (R$)"), self.juros_edit)

        self.desconto_edit = QLineEdit("0,00")
        self.desconto_edit.setMinimumHeight(38)
        form.addRow(field_label("DESCONTO (R$)"), self.desconto_edit)

        self.obs_edit = QLineEdit()
        self.obs_edit.setMinimumHeight(38)
        self.obs_edit.setPlaceholderText("Observação impressa no documento (opcional)")
        form.addRow(field_label("OBSERVAÇÃO"), self.obs_edit)
        card.body.addLayout(form)
        layout.addWidget(card)

        self.hint = QLabel("")
        self.hint.setObjectName("Muted")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancelar = button("Cancelar", ghost=True)
        cancelar.clicked.connect(self.reject)
        gerar = primary_button("Gerar documento", "receipt")
        gerar.clicked.connect(self._accept)
        actions.addWidget(cancelar)
        actions.addWidget(gerar)
        layout.addLayout(actions)

        padrao = charge_service.default_type()
        if padrao != charge_service.ASK_ALWAYS:
            indice = self.type_combo.findData(padrao)
            if indice >= 0:
                self.type_combo.setCurrentIndex(indice)
        self._type_changed()

    def _type_changed(self) -> None:
        """Mostra apenas o que interessa à modalidade escolhida."""
        tipo = self.type_combo.currentData() or TYPE_STORE
        banco = tipo == TYPE_BANK
        self.account_combo.setVisible(banco)
        self.account_label.setVisible(banco)

        if tipo == TYPE_STORE:
            self.hint.setText(
                "O documento sai para pagamento presencial. Nenhum dado bancário "
                "é impresso."
            )
        elif banco:
            self.hint.setText(
                "O documento traz os dados da conta escolhida. Só o administrador "
                "cadastra contas — o sistema nunca inventa dado bancário."
                if self.contas
                else "Nenhuma conta de recebimento cadastrada. Peça ao "
                "administrador para cadastrar em Configurações → Bancos."
            )
        else:
            self.hint.setText(
                "Boleto registrado exige integração oficial com o banco. Sem ela, "
                "a emissão é recusada — o sistema não gera linha digitável."
            )

    def _accept(self) -> None:
        self.tipo = self.type_combo.currentData() or TYPE_STORE
        if self.tipo == TYPE_BANK:
            if not self.contas:
                warn(
                    self,
                    "Conta para recebimento",
                    "Cadastre uma conta em Configurações → Bancos e recebimentos.",
                )
                return
            self.conta_id = self.account_combo.currentData()
        else:
            self.conta_id = None

        try:
            self.juros = parse_brl(self.juros_edit.text())
            self.desconto = parse_brl(self.desconto_edit.text())
        except ValueError:
            warn(self, "Valores", "Juros e desconto precisam ser valores válidos.")
            return
        self.observacao = self.obs_edit.text().strip()
        self.accept()


class ReceivePaymentDialog(QDialog):
    """Recebimento no caixa: forma de pagamento e confirmação antes de baixar."""

    def __init__(
        self, ctx: AppContext, view: charge_service.ChargeView, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.view = view
        self.payment_id: int | None = None

        self.setWindowTitle("Receber pagamento")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)
        layout.addWidget(page_header("Receber pagamento", f"Documento {view.numero}"))

        card = Card()
        for rotulo, valor in (
            ("Cliente", view.cliente),
            ("Crediário", f"{view.crediario_id:06d}"),
            ("Parcela", view.parcela),
            ("Valor", format_brl(view.valor_atualizado)),
            ("Vencimento", view.vencimento.strftime("%d/%m/%Y")),
        ):
            linha = QHBoxLayout()
            linha.addWidget(field_label(rotulo.upper()))
            destaque = QLabel(str(valor))
            destaque.setStyleSheet("font-weight: 600;")
            linha.addWidget(destaque, 1)
            card.body.addLayout(linha)
        layout.addWidget(card)

        form = QFormLayout()
        self.method_combo = QComboBox()
        self.method_combo.setMinimumHeight(38)
        for metodo in PaymentMethod:
            self.method_combo.addItem(metodo.label, metodo.value)
        form.addRow(field_label("FORMA DE PAGAMENTO"), self.method_combo)
        layout.addLayout(form)

        aviso = QLabel(
            "O funcionário registra a forma realmente usada no caixa, mesmo que o "
            "documento tenha sido emitido para pagamento presencial."
        )
        aviso.setObjectName("Muted")
        aviso.setWordWrap(True)
        layout.addWidget(aviso)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancelar = button("Cancelar", ghost=True)
        cancelar.clicked.connect(self.reject)
        confirmar = primary_button("Confirmar pagamento", "check")
        confirmar.clicked.connect(self._confirm)
        actions.addWidget(cancelar)
        actions.addWidget(confirmar)
        layout.addLayout(actions)

    def _confirm(self) -> None:
        from app.ui.widgets import confirm as ask

        forma = self.method_combo.currentData()
        rotulo = self.method_combo.currentText()
        if not ask(
            self,
            "Confirmar recebimento?",
            f"Cliente: {self.view.cliente}\n"
            f"Parcela: {self.view.parcela}\n"
            f"Valor: {format_brl(self.view.valor_atualizado)}\n"
            f"Forma de pagamento: {rotulo}\n\n"
            "Confirmar o pagamento desta parcela?",
        ):
            return

        from app.services import payment_service

        try:
            self.payment_id = payment_service.mark_as_paid(
                self.view.parcela_id,
                actor=self.ctx.user,
                forma_pagamento=forma,
                documento_id=self.view.id,
            )
        except (BusinessError, NotFoundError, PermissionDenied) as exc:
            warn(self, "Pagamento", str(exc))
            return
        self.ctx.notify(f"Pagamento registrado ({rotulo}).")
        self.accept()
