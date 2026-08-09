"""Crediários, parcelas e atrasados via API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import require_permission
from app.api.schemas import CreditDetailOut, CreditOut, DashboardOut, InstallmentOut, LateOut
from app.security.authentication import SessionUser
from app.security.permissions import Permission
from app.services import credit_service, report_service
from app.services.errors import NotFoundError

router = APIRouter(tags=["Crediários"])


@router.get("/crediarios", response_model=list[CreditOut])
def list_credits(
    busca: str = "",
    _: SessionUser = Depends(require_permission(Permission.CREDIT_VIEW)),
) -> list[CreditOut]:
    return [
        CreditOut(
            id=row.id,
            cliente=row.cliente,
            cpf=row.cpf,
            valor_total=row.valor_total,
            entrada=row.entrada,
            parcelas=row.parcelas,
            pagas=row.pagas,
            saldo=row.saldo,
            vencido=row.vencido,
        )
        for row in credit_service.list_credits(busca)
    ]


@router.get("/crediarios/{credit_id}", response_model=CreditDetailOut)
def credit_detail(
    credit_id: int,
    _: SessionUser = Depends(require_permission(Permission.CREDIT_VIEW)),
) -> CreditDetailOut:
    try:
        detail = credit_service.get_detail(credit_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CreditDetailOut(
        id=detail.id,
        cliente=detail.cliente,
        cpf=detail.cpf,
        telefone=detail.telefone,
        valor_total=detail.valor_total,
        entrada=detail.entrada,
        parcelas=detail.parcelas,
        saldo=detail.saldo,
        vencido=detail.vencido,
        itens=[
            InstallmentOut(
                id=item.id,
                parcela=item.rotulo,
                vencimento=item.vencimento,
                valor=item.valor,
                situacao=item.status,
                dias_atraso=item.dias_atraso,
                pago_em=item.pago_em,
            )
            for item in detail.installments
        ],
    )


@router.get("/atrasados", response_model=list[LateOut])
def late(
    ordem: str = "maior_valor_vencido",
    _: SessionUser = Depends(require_permission(Permission.CREDIT_VIEW)),
) -> list[LateOut]:
    return [
        LateOut(
            cliente_id=row.cliente_id,
            cliente=row.cliente,
            cpf=row.cpf,
            telefone=row.telefone,
            vencido=row.vencido,
            saldo=row.saldo,
            parcelas_vencidas=row.parcelas_vencidas,
            vencimento_antigo=row.vencimento_antigo,
            dias_atraso=row.dias_atraso,
        )
        for row in report_service.late_clients(ordem)
    ]


@router.get("/painel", response_model=DashboardOut)
def dashboard(
    _: SessionUser = Depends(require_permission(Permission.REPORT_VIEW)),
) -> DashboardOut:
    data = report_service.dashboard()
    return DashboardOut(
        total_a_receber=data.total_a_receber,
        total_vencido=data.total_vencido,
        recebido_no_mes=data.recebido_no_mes,
        clientes_em_atraso=data.clientes_em_atraso,
        parcelas_vencendo_hoje=data.parcelas_vencendo_hoje,
        parcelas_vencidas=data.parcelas_vencidas,
    )
