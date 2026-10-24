"""Configuração global da suíte.

As variáveis obrigatórias são definidas ANTES de qualquer import de `app.*`,
porque `app.main` cria a aplicação no import.

Banco dos testes:
  - padrão: SQLite em memória — a suíte roda sem Docker;
  - `TEST_DATABASE_URL=postgresql+psycopg://...`: a MESMA suíte contra um
    PostgreSQL real (ver docs/TESTES.md). As tabelas são criadas e apagadas a
    cada teste, então NUNCA aponte isto para um banco com dados.
"""

import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.main import create_app
from app.models import Base


@pytest.fixture
def engine() -> Iterator[Engine]:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        engine = create_engine(url)
    else:
        # StaticPool: o SQLite em memória existe por CONEXÃO; sem isto, cada
        # sessão veria um banco vazio diferente.
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    fabrica = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def db_de_teste() -> Iterator[Session]:
        with fabrica() as sessao:
            yield sessao

    app = create_app()
    app.dependency_overrides[get_db] = db_de_teste
    with TestClient(app) as c:
        yield c
