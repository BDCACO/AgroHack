"""Engine e sessão do SQLAlchemy.

Síncrono, e não async como no ArkoHub: lá o motivo do async era I/O concorrente
por request; aqui o trabalho pesado será análise com Pandas, que é CPU-bound e
síncrono. O FastAPI roda rotas `def` num threadpool, então o event loop não trava.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    # pool_pre_ping: conexão morta no pool (banco reiniciado) é descartada antes
    # de chegar ao request, em vez de virar 500 no primeiro uso.
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependência do FastAPI: uma sessão por request, sempre fechada no fim."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
