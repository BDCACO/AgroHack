"""Configuração global da suíte.

As variáveis obrigatórias são definidas ANTES de qualquer import de `app.*`,
porque `app.main` cria a aplicação no import. O banco padrão da suíte é SQLite
em memória: os testes unitários não dependem de Docker. O teste contra o
PostgreSQL real é o `make check-db` (ver docs/TESTES.md).
"""

import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite://")
# Forçada, e não setdefault: os testes de antes do login rodam com ela desligada, e os
# de autenticação pedem a sua (`cliente_autenticado`). Um AUTENTICACAO=true no .env do
# desenvolvedor não pode mudar o resultado da suíte.
os.environ["AUTENTICACAO"] = "false"

from collections.abc import Callable, Iterator
from functools import cache

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core import senha
from app.core.config import Settings
from app.core.database import get_db
from app.main import create_app
from app.models import Base, Usuario

# Senha de todos os usuários criados pelos testes.
SENHA = "senha-do-teste"


@pytest.fixture
def db() -> Iterator[Session]:
    """Banco novo por teste, com as tabelas dos modelos. StaticPool: uma conexão só,
    para o SQLite em memória ser o mesmo banco no teste e nas threads das rotas."""
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    # O SQLite só cumpre FOREIGN KEY (e o ON DELETE CASCADE) se pedirem, como o Postgres.
    event.listen(engine, "connect", lambda conexao, _: conexao.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine, autoflush=False, expire_on_commit=False) as sessao:
        yield sessao


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c


@pytest.fixture
def cliente_autenticado(db: Session) -> Iterator[TestClient]:
    """A API com a autenticação ligada (AUTENTICACAO=true), no mesmo banco do `client`."""
    settings = Settings(environment="test", database_url="sqlite://", autenticacao=True)
    app = create_app(settings)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c


@cache
def _hash_da_senha_do_teste() -> str:
    # O Argon2id leva uns 0,1 s de propósito: um hash só para a suíte inteira.
    return senha.gerar_hash(SENHA)


type CriarUsuario = Callable[..., Usuario]


@pytest.fixture
def criar_usuario(db: Session) -> CriarUsuario:
    """Cadastra direto no banco, com a senha `SENHA`."""

    def criar(login: str = "ze", papel: str = "funcionario", **campos: object) -> Usuario:
        usuario = Usuario(
            nome=campos.pop("nome", login.title()),
            login=login,
            papel=papel,
            senha_hash=_hash_da_senha_do_teste(),
            **campos,
        )
        db.add(usuario)
        db.commit()
        return usuario

    return criar


def erro_inesperado(caplog: pytest.LogCaptureFixture) -> BaseException:
    """O erro que virou 500: a API responde com frase e id, e o erro em si vai só para o
    log (`app.erro`, com o traceback). É por ele que o teste confere o que quebrou."""
    erros = [r for r in caplog.records if r.name == "app.erro" and r.exc_info]
    assert erros, "nenhum erro inesperado no log"
    return erros[-1].exc_info[1]  # type: ignore[index]


def entrar(cliente: TestClient, login: str, senha_digitada: str = SENHA) -> dict[str, str]:
    """Faz login e devolve o cabeçalho com o token, pronto para os pedidos."""
    resposta = cliente.post("/api/v1/auth/entrar", json={"login": login, "senha": senha_digitada})
    assert resposta.status_code == 200, resposta.text
    return {"Authorization": f"Bearer {resposta.json()['token']}"}
