"""Configuração global da suíte.

As variáveis obrigatórias são definidas ANTES de qualquer import de `app.*`,
porque `app.main` cria a aplicação no import. O banco padrão da suíte é SQLite
em memória: os testes unitários não dependem de Docker. O teste contra o
PostgreSQL real é o `make check-db` (ver docs/TESTES.md).
"""

import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c
