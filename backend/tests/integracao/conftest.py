"""Testes de integração: a API de verdade (uvicorn, num processo à parte) contra um
PostgreSQL de verdade, com o schema criado pelas migrations do Alembic, e não pelos
modelos. Os testes falam HTTP com o servidor, como o site e o app.

Só rodam com `INTEGRACAO_DATABASE_URL` apontando para um banco DESCARTÁVEL: o schema
`public` dele é apagado e recriado no início da sessão. Sem a variável, são pulados, e a
suíte comum continua sem depender de Docker. Ver docs/TESTES.md.

Dois papéis, como no container: a URL dada é a do DONO (superusuário do PostgreSQL de
teste), que roda as migrations e prepara cada teste; a API sobe com o papel da aplicação
(`PAPEL_DA_APP`), criado pelo comando de verdade (`python -m app.papel_da_aplicacao`), com
uma senha nova a cada sessão. Senão, os testes provariam a API com poderes que ela não
tem no container.
"""

import os
import secrets
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import Engine, create_engine, make_url, text

from app.models import Base

URL_DO_BANCO = os.environ.get("INTEGRACAO_DATABASE_URL", "")
BACKEND = Path(__file__).resolve().parents[2]
# Papel do cluster inteiro, e não só do banco: o nome não é o do papel do `make up`
# (campocerto_app), para o `make test-integracao` não mexer na senha dele.
PAPEL_DA_APP = "campocerto_app_teste"
URL_DA_APP = (
    make_url(URL_DO_BANCO)
    .set(username=PAPEL_DA_APP, password=secrets.token_hex(16))
    .render_as_string(hide_password=False)
    if URL_DO_BANCO
    else ""
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if URL_DO_BANCO:
        return
    pular = pytest.mark.skip(reason="defina INTEGRACAO_DATABASE_URL (banco descartável)")
    for item in items:
        if "integracao" in item.path.parts:
            item.add_marker(pular)


def ambiente_do_entrypoint(**variaveis: str) -> dict[str, str]:
    """As duas URLs, como o compose as dá ao container: a da API (papel da aplicação) e a
    das migrations (o dono)."""
    return (
        os.environ
        | {
            "ENVIRONMENT": "test",
            "DATABASE_URL": URL_DA_APP,
            "MIGRATIONS_DATABASE_URL": URL_DO_BANCO,
        }
        | variaveis
    )


def alembic(*argumentos: str, **variaveis: str) -> subprocess.CompletedProcess[str]:
    """O Alembic como no entrypoint do container: um processo à parte, com o banco no
    ambiente. Falhou, o teste vê a saída inteira."""
    return subprocess.run(  # noqa: S603 — comando fixo, sem entrada de usuário
        [sys.executable, "-m", "alembic", *argumentos],
        cwd=BACKEND,
        env=ambiente_do_entrypoint(**variaveis),
        capture_output=True,
        text=True,
        check=True,
    )


def garantir_o_papel_da_aplicacao() -> subprocess.CompletedProcess[str]:
    """O comando do entrypoint, depois das migrations."""
    return subprocess.run(
        [sys.executable, "-m", "app.papel_da_aplicacao"],
        cwd=BACKEND,
        env=ambiente_do_entrypoint(),
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture(scope="session")
def banco() -> Iterator[Engine]:
    """O banco visto pelo dono: prepara e confere cada teste por fora da API."""
    engine = create_engine(URL_DO_BANCO)
    with engine.begin() as conexao:
        conexao.execute(text("DROP SCHEMA public CASCADE"))
        conexao.execute(text("CREATE SCHEMA public"))
    alembic("upgrade", "head")
    garantir_o_papel_da_aplicacao()
    yield engine
    engine.dispose()


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def subir_uvicorn(**variaveis: str) -> Iterator[str]:
    """O uvicorn de produção (sem --reload) servindo a API com o papel da aplicação e as
    variáveis dadas no ambiente; devolve a URL base da v1 e derruba o processo no fim."""
    porta = _porta_livre()
    ambiente = (
        os.environ
        | {
            "ENVIRONMENT": "test",
            "DATABASE_URL": URL_DA_APP,
            "LOG_LEVEL": "WARNING",
            # Os servidores da sessão atendem a suíte inteira, toda de 127.0.0.1: com o
            # limite por IP, um teste gastaria a cota do outro. Quem prova o limite sobe o
            # seu, com ele ligado (test_blindagem_da_api.py).
            "LIMITE_POR_IP": "false",
        }
        | variaveis
    )
    # Como no container (o entrypoint a tira antes do uvicorn): a API não tem a do dono.
    ambiente.pop("MIGRATIONS_DATABASE_URL", None)
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


@pytest.fixture(scope="session")
def servidor(banco: Engine) -> Iterator[str]:
    """A API como o site e o app de hoje a usam: sem login (AUTENTICACAO=false)."""
    yield from subir_uvicorn(AUTENTICACAO="false")


@pytest.fixture(scope="session")
def servidor_autenticado(banco: Engine) -> Iterator[str]:
    """A mesma API, no mesmo banco, com o login ligado (AUTENTICACAO=true)."""
    yield from subir_uvicorn(AUTENTICACAO="true")


def _banco_vazio(banco: Engine) -> None:
    tabelas = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with banco.begin() as conexao:
        conexao.execute(text(f"TRUNCATE {tabelas} RESTART IDENTITY CASCADE"))


@pytest.fixture
def api(servidor: str, banco: Engine) -> Iterator[httpx.Client]:
    """Cliente HTTP contra o servidor, com o banco vazio (as tabelas dos modelos, sem a
    do Alembic) a cada teste."""
    _banco_vazio(banco)
    with httpx.Client(base_url=servidor, timeout=30) as cliente:
        yield cliente


@pytest.fixture
def api_autenticada(servidor_autenticado: str, banco: Engine) -> Iterator[httpx.Client]:
    """Como `api`, contra o servidor com o login ligado. Sem token: cada teste entra."""
    _banco_vazio(banco)
    with httpx.Client(base_url=servidor_autenticado, timeout=30) as cliente:
        yield cliente
