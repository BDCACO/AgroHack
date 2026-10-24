"""A conexão da API com o banco: os tempos-limite e o pool. O efeito de verdade (a consulta
cortada, a trava que desiste) está em tests/integracao/test_banco_privilegio_e_tempos.py;
aqui, o que a configuração manda ao driver."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.database import argumentos_do_engine

POSTGRES = "postgresql+psycopg://campocerto_app:abc123@db:5432/campocerto"


def test_tempos_limite_tem_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    for nome in (
        "DB_STATEMENT_TIMEOUT_MS",
        "DB_LOCK_TIMEOUT_MS",
        "DB_IDLE_IN_TRANSACTION_TIMEOUT_MS",
        "DB_POOL_TIMEOUT_S",
    ):
        monkeypatch.delenv(nome, raising=False)

    settings = Settings(environment="test", database_url=POSTGRES, _env_file=None)

    assert settings.db_statement_timeout_ms == 30_000
    assert settings.db_lock_timeout_ms == 5_000
    assert settings.db_idle_in_transaction_timeout_ms == 60_000
    assert settings.db_pool_timeout_s == 10


@pytest.mark.parametrize(
    "variavel",
    ["DB_STATEMENT_TIMEOUT_MS", "DB_LOCK_TIMEOUT_MS", "DB_IDLE_IN_TRANSACTION_TIMEOUT_MS"],
)
@pytest.mark.parametrize("valor", ["0", "-1", "cinco"])
def test_tempo_limite_nao_se_desliga(
    monkeypatch: pytest.MonkeyPatch, variavel: str, valor: str
) -> None:
    # Zero, no PostgreSQL, é "sem limite": desligar seria voltar à API que fica pendurada.
    monkeypatch.setenv(variavel, valor)

    with pytest.raises(ValidationError):
        Settings(environment="test", database_url=POSTGRES, _env_file=None)


def test_postgres_recebe_os_tempos_limite_na_conexao() -> None:
    settings = Settings(
        environment="test",
        database_url=POSTGRES,
        db_statement_timeout_ms=30_000,
        db_lock_timeout_ms=5_000,
        db_idle_in_transaction_timeout_ms=60_000,
        db_pool_timeout_s=10,
    )

    argumentos = argumentos_do_engine(settings)

    assert argumentos["connect_args"] == {
        "options": "-c statement_timeout=30000 -c lock_timeout=5000"
        " -c idle_in_transaction_session_timeout=60000"
    }
    assert argumentos["pool_timeout"] == 10
    assert argumentos["pool_recycle"] > 0
    assert argumentos["pool_pre_ping"] is True


def test_sqlite_dos_testes_nao_recebe_opcoes_do_postgres() -> None:
    settings = Settings(environment="test", database_url="sqlite://")

    assert argumentos_do_engine(settings) == {"pool_pre_ping": True}
