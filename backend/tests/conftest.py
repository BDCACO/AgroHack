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
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.main import create_app
from app.models import Base


@pytest.fixture
def db() -> Iterator[Session]:
    """Banco novo por teste, com as tabelas dos modelos. StaticPool: uma conexão só,
    para o SQLite em memória ser o mesmo banco no teste e nas threads das rotas."""
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    with Session(engine, autoflush=False, expire_on_commit=False) as sessao:
        yield sessao


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
