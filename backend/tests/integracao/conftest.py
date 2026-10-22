"""Testes de integração: a API de verdade (uvicorn, num processo à parte) contra um
PostgreSQL de verdade, com o schema criado pelas migrations do Alembic, e não pelos
modelos. Os testes falam HTTP com o servidor, como o site e o app.

Só rodam com `INTEGRACAO_DATABASE_URL` apontando para um banco DESCARTÁVEL: o schema
`public` dele é apagado e recriado no início da sessão. Sem a variável, são pulados, e a
suíte comum continua sem depender de Docker. Ver docs/TESTES.md.
"""

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import Engine, create_engine, text

from app.models import Base

URL_DO_BANCO = os.environ.get("INTEGRACAO_DATABASE_URL", "")
BACKEND = Path(__file__).resolve().parents[2]


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if URL_DO_BANCO:
        return
    pular = pytest.mark.skip(reason="defina INTEGRACAO_DATABASE_URL (banco descartável)")
    for item in items:
        if "integracao" in item.path.parts:
            item.add_marker(pular)


def alembic(*argumentos: str) -> subprocess.CompletedProcess[str]:
    """O Alembic como no entrypoint do container: um processo à parte, com o banco no
    ambiente. Falhou, o teste vê a saída inteira."""
    ambiente = os.environ | {"ENVIRONMENT": "test", "DATABASE_URL": URL_DO_BANCO}
    return subprocess.run(  # noqa: S603 — comando fixo, sem entrada de usuário
        [sys.executable, "-m", "alembic", *argumentos],
        cwd=BACKEND,
        env=ambiente,
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture(scope="session")
def banco() -> Iterator[Engine]:
    engine = create_engine(URL_DO_BANCO)
    with engine.begin() as conexao:
        conexao.execute(text("DROP SCHEMA public CASCADE"))
        conexao.execute(text("CREATE SCHEMA public"))
    alembic("upgrade", "head")
    yield engine
    engine.dispose()


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def servidor(banco: Engine) -> Iterator[str]:
    """O uvicorn de produção (sem --reload) servindo a API; devolve a URL base da v1."""
    porta = _porta_livre()
    ambiente = os.environ | {
        "ENVIRONMENT": "test",
        "DATABASE_URL": URL_DO_BANCO,
        "LOG_LEVEL": "WARNING",
    }
    processo = subprocess.Popen(  # noqa: S603 — comando fixo
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(porta)],
        cwd=BACKEND,
        env=ambiente,
    )
    base = f"http://127.0.0.1:{porta}/api/v1"
    try:
        for _ in range(100):
            try:
                if httpx.get(f"{base}/ready", timeout=1).status_code == 200:
                    break
            except httpx.TransportError:
                pass
            if processo.poll() is not None:
                pytest.fail("o uvicorn saiu antes de responder")
            time.sleep(0.1)
        else:
            pytest.fail("o uvicorn não respondeu /ready em 10 s")
        yield base
    finally:
        processo.terminate()
        processo.wait(timeout=10)


@pytest.fixture
def api(servidor: str, banco: Engine) -> Iterator[httpx.Client]:
    """Cliente HTTP contra o servidor, com o banco vazio (as tabelas dos modelos, sem a
    do Alembic) a cada teste."""
    tabelas = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with banco.begin() as conexao:
        conexao.execute(text(f"TRUNCATE {tabelas} RESTART IDENTITY CASCADE"))
    with httpx.Client(base_url=servidor, timeout=30) as cliente:
        yield cliente
