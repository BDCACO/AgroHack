"""A conexão da API com o banco: os tempos-limite e o pool. O efeito de verdade (a consulta
cortada, a trava que desiste) está em tests/integracao/test_banco_privilegio_e_tempos.py;
aqui, o que a configuração manda ao driver."""

import logging
from typing import Any
from uuid import uuid4

import psycopg
import pytest
import sqlalchemy.exc
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import argumentos_do_engine
from app.core.relogio import hoje
from app.services import estoque

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


def _rota_que_estoura(client: TestClient, erro: Exception) -> None:
    def estourar() -> None:
        raise erro

    client.app.add_api_route("/api/v1/teste-estoura", estourar)


@pytest.mark.parametrize(
    ("causa", "frase"),
    [
        (psycopg.errors.QueryCanceled("canceling statement due to statement timeout"), "demorou"),
        (psycopg.errors.LockNotAvailable("canceling statement due to lock timeout"), "outro"),
    ],
)
def test_tempo_limite_do_banco_vira_503_com_retry_after(
    client: TestClient, caplog: pytest.LogCaptureFixture, causa: Exception, frase: str
) -> None:
    # Não é defeito do servidor nem do pedido: é espera, e passa. 503 com Retry-After diz
    # "tente de novo daqui a pouco", e a frase vai para a tela do site e do app.
    _rota_que_estoura(client, OperationalError("SELECT 'segredo'", {"senha": "x"}, causa))

    with caplog.at_level(logging.WARNING):
        resposta = client.get("/api/v1/teste-estoura")

    assert resposta.status_code == 503
    assert resposta.headers["Retry-After"] == "5"
    assert frase in resposta.json()["detail"].lower()
    assert "tente de novo" in resposta.json()["detail"].lower()
    # O log diz o que houve, sem a consulta nem os valores dela.
    assert causa.sqlstate in caplog.text
    assert "segredo" not in caplog.text


def test_pool_sem_conexao_livre_vira_503(client: TestClient) -> None:
    _rota_que_estoura(client, sqlalchemy.exc.TimeoutError("QueuePool limit reached"))

    resposta = client.get("/api/v1/teste-estoura")

    assert resposta.status_code == 503
    assert resposta.headers["Retry-After"] == "5"


def test_outro_erro_operacional_continua_erro_do_servidor(client: TestClient) -> None:
    # Banco fora do ar, senha errada: não é espera que passa sozinha, e esconder num 503
    # "tente de novo" atrasaria quem precisa consertar.
    _rota_que_estoura(client, OperationalError("SELECT 1", {}, Exception("conexão recusada")))

    with pytest.raises(OperationalError):
        client.get("/api/v1/teste-estoura")


def test_lote_que_estoura_o_tempo_para_e_o_app_reenvia(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O item que estoura o tempo não vira `recusada`: o dado dele está certo, só esperou
    demais, e `recusada` pede ao produtor que confira e lance de novo. O lote inteiro
    responde 503; o que já foi gravado fica (cada item tem a sua transação), e o reenvio,
    que o app faz sozinho, devolve-o como `ja_existia`."""
    insumo = client.post("/api/v1/insumos", json={"nome": "Ureia", "unidade": "kg"}).json()["id"]
    lote = [
        {
            "uuid": str(uuid4()),
            "insumo_id": insumo,
            "tipo": "entrada",
            "data": str(hoje()),
            "quantidade": quantidade,
        }
        for quantidade in (10, 20)
    ]
    original = estoque.registrar_movimentacao

    def segunda_espera_demais(db: Session, dados: Any, usuario_id: int | None) -> Any:
        if dados.quantidade == 20:
            trava = psycopg.errors.LockNotAvailable("canceling statement due to lock timeout")
            raise OperationalError("INSERT", {}, trava)
        return original(db, dados, usuario_id)

    monkeypatch.setattr(estoque, "registrar_movimentacao", segunda_espera_demais)
    resposta = client.post("/api/v1/movimentacoes/lote", json={"movimentacoes": lote})

    assert resposta.status_code == 503
    assert resposta.headers["Retry-After"] == "5"

    monkeypatch.setattr(estoque, "registrar_movimentacao", original)
    reenvio = client.post("/api/v1/movimentacoes/lote", json={"movimentacoes": lote}).json()
    assert [r["situacao"] for r in reenvio["resultados"]] == ["ja_existia", "gravada"]


def test_migrations_usam_a_url_do_dono_quando_vem(monkeypatch: pytest.MonkeyPatch) -> None:
    dono = "postgresql+psycopg://campocerto:abc123@db:5432/campocerto"
    monkeypatch.setenv("MIGRATIONS_DATABASE_URL", dono)

    settings = Settings(environment="test", database_url=POSTGRES, _env_file=None)

    assert settings.url_das_migrations == dono


def test_sem_url_de_migrations_usa_a_da_api(monkeypatch: pytest.MonkeyPatch) -> None:
    # A vida fácil do desenvolvimento: quem roda tudo com um papel só (uv run no host, o
    # SQLite dos testes) não precisa de uma segunda variável. Em produção, a API conectada
    # como dono não sobe (ver app/main.py), e as migrations com o papel da aplicação falham
    # por falta de permissão: os dois erros são altos, nenhum é silencioso.
    monkeypatch.delenv("MIGRATIONS_DATABASE_URL", raising=False)

    settings = Settings(environment="test", database_url=POSTGRES, _env_file=None)

    assert settings.url_das_migrations == POSTGRES
