"""Engine e sessão do SQLAlchemy.

Síncrono, e não async como no ArkoHub: lá o motivo do async era I/O concorrente
por request; aqui o trabalho pesado é análise e leitura de planilhas, CPU-bound e
síncrono. O FastAPI roda rotas `def` num threadpool, então o event loop não trava.
"""

from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, create_engine, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings

# Meia hora: o PostgreSQL não derruba conexão parada, mas firewall e proxy no meio do
# caminho derrubam, sem avisar. Renovar de tempos em tempos sai mais barato que descobrir
# no pedido.
RECICLAR_CONEXAO_S = 1800


def argumentos_do_engine(settings: Settings) -> dict[str, Any]:
    """O que a API passa ao `create_engine`. Os tempos-limite vão na conexão, e não no
    papel do banco (`ALTER ROLE ... SET`): ficam no `config.py`, validados no boot, e
    valem para tudo que usa este engine (a API, a demonstração, o `criar-dono`). O
    Alembic tem o próprio engine, sem eles: migration pode demorar."""
    # pool_pre_ping: conexão morta no pool (banco reiniciado) é descartada antes
    # de chegar ao request, em vez de virar 500 no primeiro uso.
    argumentos: dict[str, Any] = {"pool_pre_ping": True}
    if make_url(settings.database_url).get_backend_name() != "postgresql":
        # O SQLite dos testes não tem essas opções nem esse pool.
        return argumentos
    opcoes = (
        f"-c statement_timeout={settings.db_statement_timeout_ms}"
        f" -c lock_timeout={settings.db_lock_timeout_ms}"
        f" -c idle_in_transaction_session_timeout={settings.db_idle_in_transaction_timeout_ms}"
    )
    return argumentos | {
        "connect_args": {"options": opcoes},
        "pool_timeout": settings.db_pool_timeout_s,
        "pool_recycle": RECICLAR_CONEXAO_S,
    }


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.database_url, **argumentos_do_engine(settings))


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def violou_nome_unico(erro: IntegrityError, tabela: str) -> bool:
    """Se a violação foi a do nome único da tabela, e não outra regra do banco. O
    PostgreSQL diz o nome da constraint; o SQLite dos testes, a coluna."""
    mensagem = str(erro.orig)
    return f"uq_{tabela}_nome" in mensagem or f"{tabela}.nome" in mensagem


def get_db() -> Iterator[Session]:
    """Dependência do FastAPI: uma sessão por request, sempre fechada no fim."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
