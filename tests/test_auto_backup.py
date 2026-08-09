"""Backup automático: intervalo, retenção e tolerância a falha de destino."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.config import APP_SLUG
from app.database.connection import session_scope
from app.models.setting import Setting
from app.models.status import Role
from app.security.permissions import PermissionDenied
from app.services import backup_service, user_service
from app.services.errors import BusinessError


def _autos(folder):  # noqa: ANN001
    return sorted(folder.glob(f"{APP_SLUG}_Auto_*.db"))


def _set_last_run(quando: datetime | None) -> None:
    with session_scope() as session:
        row = session.get(Setting, backup_service.KEY_AUTO_LAST)
        valor = quando.isoformat(timespec="seconds") if quando else ""
        if row is None:
            session.add(Setting(chave=backup_service.KEY_AUTO_LAST, valor=valor))
        else:
            row.valor = valor


def test_padrao_e_ligado_uma_vez_por_dia(admin):
    config = backup_service.auto_config()
    assert config.enabled is True
    assert config.interval_hours == 24
    assert config.keep == 15
    assert config.last_run is None
    assert config.due is True, "sem backup anterior, deve rodar na primeira abertura"


def test_primeira_execucao_cria_o_arquivo(admin):
    caminho = backup_service.auto_backup_if_due()
    assert caminho is not None
    assert caminho.exists()
    assert caminho.name.startswith(f"{APP_SLUG}_Auto_")
    assert backup_service.auto_config().last_run is not None


def test_nao_repete_antes_do_intervalo(admin):
    backup_service.auto_backup_if_due()
    assert backup_service.auto_backup_if_due() is None, "não venceu o intervalo"


def test_roda_de_novo_quando_o_intervalo_vence(admin):
    backup_service.auto_backup_if_due()
    _set_last_run(datetime.now() - timedelta(hours=25))
    assert backup_service.auto_config().due is True
    assert backup_service.auto_backup_if_due() is not None


def test_desligado_nao_cria_nada(admin):
    backup_service.save_auto_config(False, 24, None, 15, admin)
    assert backup_service.auto_config().due is False
    assert backup_service.auto_backup_if_due() is None


def test_retencao_apaga_apenas_as_copias_automaticas(admin):
    """Backup manual e cópia de pré-restauração não podem ser removidos."""
    manual = backup_service.create_backup(actor=admin)
    pasta = backup_service.auto_config().folder
    reserva = pasta / f"{APP_SLUG}_AntesDaRestauracao_teste.db"
    reserva.write_bytes(manual.read_bytes())

    backup_service.save_auto_config(True, 1, None, 2, admin)
    momentos = [datetime(2026, 8, 1, 10, 0, 0) + timedelta(minutes=i) for i in range(5)]
    for indice, _ in enumerate(momentos):
        # Nomes distintos: o serviço usa segundos, então forçamos arquivos únicos.
        destino = pasta / f"{APP_SLUG}_Auto_2026-08-01_1000{indice:02d}.db"
        destino.write_bytes(manual.read_bytes())

    backup_service.auto_backup_if_due(force=True)

    assert len(_autos(pasta)) == 2, "deve manter apenas as 2 mais recentes"
    assert manual.exists(), "backup manual não pode ser apagado"
    assert reserva.exists(), "cópia de segurança não pode ser apagada"


def test_pasta_configuravel(admin, tmp_path):
    destino = tmp_path / "pendrive"
    backup_service.save_auto_config(True, 1, destino, 5, admin)
    assert backup_service.auto_config().folder == destino

    caminho = backup_service.auto_backup_if_due(force=True)
    assert caminho is not None
    assert caminho.parent == destino


def test_destino_indisponivel_nao_derruba_o_sistema(admin, tmp_path):
    """Pen drive removido não pode impedir o programa de abrir."""
    bloqueio = tmp_path / "arquivo_no_lugar_da_pasta"
    bloqueio.write_text("isto e um arquivo, nao uma pasta", encoding="utf-8")

    with session_scope() as session:
        session.add(
            Setting(chave=backup_service.KEY_AUTO_FOLDER, valor=str(bloqueio / "sub"))
        )

    assert backup_service.auto_backup_if_due(force=True) is None


def test_configuracao_invalida_e_recusada(admin):
    with pytest.raises(BusinessError):
        backup_service.save_auto_config(True, 0, None, 5, admin)
    with pytest.raises(BusinessError):
        backup_service.save_auto_config(True, 24, None, 0, admin)


def test_funcionario_nao_configura_backup(admin):
    user_service.create_user("Ana Vendas", "ana", "senha123", Role.STAFF, admin)
    funcionario = user_service.authenticate("ana", "senha123")
    with pytest.raises(PermissionDenied):
        backup_service.save_auto_config(True, 12, None, 5, funcionario)
