"""Ambiente do Alembic.

Diferente do ArkoHub, `target_metadata` aponta para os modelos: lá o autogenerate
foi recusado porque não enxerga Row-Level Security; aqui não há RLS nem
multi-tenancy, e o autogenerate poupa trabalho. Toda migration gerada é REVISADA
antes do commit — o autogenerate não detecta rename de coluna, por exemplo.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import get_settings
from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# A URL do dono do schema (MIGRATIONS_DATABASE_URL), e não a da API: o papel da aplicação
# não cria nem altera tabela. Este engine também não leva os tempos-limite da API
# (app/core/database.py): migration pode demorar.
# Direto ao engine, e não pelo `config.set_main_option`: o configparser do Alembic lê "%"
# como interpolação, e a senha com "%" ou "@" (que na URL vira "%40") derrubava o comando
# com um ValueError que imprimia a URL inteira, com a senha.
URL_DAS_MIGRATIONS = get_settings().url_das_migrations

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=URL_DAS_MIGRATIONS,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(URL_DAS_MIGRATIONS, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
