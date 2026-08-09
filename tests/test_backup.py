"""Backup, validação do arquivo e restauração."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services import backup_service, client_service
from app.services.errors import BusinessError


def test_criar_backup(admin, cliente, tmp_path):
    destino = tmp_path / "backup_sys.db"
    caminho = backup_service.create_backup(destino, admin)

    assert caminho.exists()
    assert caminho.stat().st_size > 0
    assert backup_service.looks_like_sys_backup(caminho)


def test_arquivo_estranho_nao_e_aceito(tmp_path):
    falso = tmp_path / "planilha.db"
    falso.write_bytes(b"isto nao e um banco de dados" * 40)
    assert not backup_service.looks_like_sys_backup(falso)


def test_restauracao_recupera_os_dados(admin, cliente, tmp_path):
    backup = backup_service.create_backup(tmp_path / "antes.db", admin)

    client_service.create_client(
        "Cliente Posterior", "168.995.350-09", "62999990000", admin
    )
    assert len(client_service.list_clients()) == 2

    seguranca = backup_service.restore_backup(backup, admin)

    clientes = client_service.list_clients()
    assert len(clientes) == 1
    assert clientes[0].cpf == "529.982.247-25"
    assert seguranca.exists()


def test_restaurar_arquivo_invalido_falha(admin, tmp_path):
    ruim = tmp_path / "qualquer.db"
    ruim.write_text("conteúdo inválido", encoding="utf-8")
    with pytest.raises(BusinessError):
        backup_service.restore_backup(ruim, admin)


def test_backup_de_versao_antiga_e_migrado_na_restauracao(admin, cliente, tmp_path):
    """Restaurar um arquivo gerado por versão anterior não pode deixar o banco velho."""
    import sqlalchemy as sa

    from app.database.connection import get_engine
    from app.models.payment import UNIQUE_PAYMENT_INDEX

    backup = backup_service.create_backup(tmp_path / "versao_antiga.db", admin)

    # Deixa o arquivo de backup no formato anterior, sem o índice único.
    antigo = sa.create_engine(f"sqlite:///{backup}")
    with antigo.begin() as connection:
        connection.execute(sa.text(f"DROP INDEX {UNIQUE_PAYMENT_INDEX}"))
    antigo.dispose()

    backup_service.restore_backup(backup, admin)

    indices = {i["name"] for i in sa.inspect(get_engine()).get_indexes("pagamentos")}
    assert UNIQUE_PAYMENT_INDEX in indices


def test_nome_padrao_do_backup():
    nome = backup_service.default_backup_name()
    assert nome.startswith("SYS_Crediario_Backup_")
    assert nome.endswith(".db")


def test_saldo_preservado_apos_restauracao(admin, cliente, tmp_path):
    from datetime import date

    from app.services import credit_service

    credit_service.create_credit(
        cliente_id=cliente,
        valor_total=Decimal("300.00"),
        entrada=Decimal("0.00"),
        parcelas=3,
        primeiro_vencimento=date.today(),
        actor=admin,
    )
    backup = backup_service.create_backup(tmp_path / "com_crediario.db", admin)
    backup_service.restore_backup(backup, admin)

    resumo = client_service.get_summary(cliente)
    assert resumo.saldo_devedor == Decimal("300.00")
