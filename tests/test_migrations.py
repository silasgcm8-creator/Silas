"""Migração de bancos já existentes (dados de clientes reais em produção)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import sqlalchemy as sa

from app.config import SCHEMA_VERSION
from app.database.connection import get_engine, session_scope
from app.database.migrations import KEY_SCHEMA, run_migrations
from app.models.payment import UNIQUE_PAYMENT_INDEX
from app.models.setting import Setting
from app.services import credit_service, payment_service


def _indexes() -> set[str]:
    return {index["name"] for index in sa.inspect(get_engine()).get_indexes("pagamentos")}


def _simulate_old_database(indice_sem_condicao: bool = False) -> None:
    """Volta o banco ao formato anterior: sem índice parcial e em versão antiga.

    Com `indice_sem_condicao`, recria o índice como era na versão 2 — único mas
    sem a condição `estornado_em IS NULL`.
    """
    with get_engine().begin() as connection:
        connection.execute(sa.text(f"DROP INDEX {UNIQUE_PAYMENT_INDEX}"))
        if indice_sem_condicao:
            connection.execute(
                sa.text(
                    f"CREATE UNIQUE INDEX {UNIQUE_PAYMENT_INDEX} "
                    "ON pagamentos (parcela_id)"
                )
            )
    with session_scope() as session:
        session.get(Setting, KEY_SCHEMA).valor = "1"


def _index_definition() -> str:
    with get_engine().connect() as connection:
        return str(
            connection.execute(
                sa.text("SELECT sql FROM sqlite_master WHERE name = :n"),
                {"n": UNIQUE_PAYMENT_INDEX},
            ).scalar()
            or ""
        )


def test_banco_novo_ja_nasce_com_o_indice_unico():
    assert UNIQUE_PAYMENT_INDEX in _indexes()


def test_versao_do_esquema_fica_registrada():
    with session_scope() as session:
        assert session.get(Setting, KEY_SCHEMA).valor == str(SCHEMA_VERSION)


def test_migracao_limpa_pagamento_duplicado_e_cria_o_indice(admin, cliente):
    """Banco antigo pode ter dois recebimentos da mesma parcela inflando o caixa."""
    crediario = credit_service.create_credit(
        cliente_id=cliente,
        valor_total=Decimal("600.00"),
        entrada=Decimal("0.00"),
        parcelas=3,
        primeiro_vencimento=date.today() - timedelta(days=18),
        actor=admin,
    )
    parcela = credit_service.get_detail(crediario).installments[0]
    payment_service.mark_as_paid(parcela.id, admin)

    _simulate_old_database()

    # Duplicata que só era possível antes do índice único existir.
    with get_engine().begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO pagamentos (parcela_id, crediario_id, cliente_id, valor, "
                "data_pagamento, usuario_nome, criado_em, codigo, forma_pagamento) "
                "VALUES (:p, :c, :cl, :v, :d, 'duplicado', :agora, '', '')"
            ),
            {
                "p": parcela.id,
                "c": crediario,
                "cl": cliente,
                "v": 20000,
                "d": date.today(),
                "agora": datetime.now(),
            },
        )

    hoje = date.today()
    assert payment_service.total_received(hoje, hoje) == Decimal("400.00")  # caixa inflado

    run_migrations()

    assert UNIQUE_PAYMENT_INDEX in _indexes()
    assert payment_service.total_received(hoje, hoje) == Decimal("200.00")
    with session_scope() as session:
        assert session.get(Setting, KEY_SCHEMA).valor == str(SCHEMA_VERSION)


def test_indice_da_versao_anterior_ganha_a_condicao_de_estorno(admin, cliente):
    """Sem a condição, uma parcela estornada nunca mais poderia ser paga."""
    _simulate_old_database(indice_sem_condicao=True)
    assert "estornado_em" not in _index_definition()

    run_migrations()

    assert "estornado_em" in _index_definition()


def test_migracao_da_codigo_aos_recebimentos_antigos(admin, cliente):
    """Recebimentos gravados antes do código da operação não ficam sem número."""
    import sqlalchemy as sa2

    crediario = credit_service.create_credit(
        cliente_id=cliente,
        valor_total=Decimal("300.00"),
        entrada=Decimal("0.00"),
        parcelas=3,
        primeiro_vencimento=date.today(),
        actor=admin,
    )
    parcela = credit_service.get_detail(crediario).installments[0]
    payment_service.mark_as_paid(parcela.id, admin)

    # Apaga o código, como estaria num banco da versão anterior.
    with get_engine().begin() as connection:
        connection.execute(sa2.text("UPDATE pagamentos SET codigo = ''"))

    run_migrations()

    with get_engine().connect() as connection:
        codigo = connection.execute(sa2.text("SELECT codigo FROM pagamentos")).scalar()
    assert codigo and codigo.startswith("PAG-")


def test_migracao_pode_rodar_duas_vezes(admin):
    """Reabrir o programa não pode falhar por índice já existente."""
    run_migrations()
    run_migrations()
    assert UNIQUE_PAYMENT_INDEX in _indexes()
