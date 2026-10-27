"""O comando que garante o papel da aplicação no PostgreSQL (`python -m
app.papel_da_aplicacao`): aqui, o que ele lê da configuração e recusa antes de tocar o
banco. O que ele faz no banco (o papel sem poder de DDL, as permissões que nascem com as
tabelas novas) está em tests/integracao/test_banco_privilegio_e_tempos.py."""

import pytest

from app.core.config import Settings
from app.papel_da_aplicacao import ConfiguracaoInvalida, ler_papeis

DONO = "postgresql+psycopg://campocerto:senhaDoDono123@db:5432/campocerto"


def configuracao(api: str, migrations: str | None = DONO) -> Settings:
    return Settings(environment="test", database_url=api, migrations_database_url=migrations)


def test_le_o_papel_e_a_senha_da_url_da_api() -> None:
    papeis = ler_papeis(
        configuracao("postgresql+psycopg://campocerto_app:senhaDaApp2026@db:5432/campocerto")
    )

    assert papeis is not None
    assert papeis.papel == "campocerto_app"
    assert papeis.senha == "senhaDaApp2026"
    assert papeis.url_do_dono.username == "campocerto"


@pytest.mark.parametrize(
    "migrations",
    [None, "postgresql+psycopg://campocerto_app:outraSenha12@db:5432/campocerto"],
)
def test_com_um_papel_so_nao_ha_o_que_garantir(migrations: str | None) -> None:
    # O desenvolvimento com um papel só (sem MIGRATIONS_DATABASE_URL, ou as duas com o mesmo
    # usuário): mexer nas permissões do próprio dono o deixaria sem poder de DDL.
    api = "postgresql+psycopg://campocerto_app:senhaDaApp2026@db:5432/campocerto"

    assert ler_papeis(configuracao(api, migrations)) is None


@pytest.mark.parametrize(
    "senha",
    [
        "troque-esta",  # o hífen
        "senha@dela12345",  # a arroba quebra a URL
        "curta1",  # menos de 12
        "acentuação12345",
    ],
)
def test_senha_so_com_letras_e_numeros(senha: str) -> None:
    api = f"postgresql+psycopg://campocerto_app:{senha}@db:5432/campocerto"

    with pytest.raises(ConfiguracaoInvalida, match="APP_DB_PASSWORD") as recusa:
        ler_papeis(configuracao(api))
    # A mensagem vai para o log do container: nunca a senha.
    assert senha not in str(recusa.value)


def test_url_sem_senha_e_recusada() -> None:
    with pytest.raises(ConfiguracaoInvalida, match="APP_DB_PASSWORD"):
        ler_papeis(configuracao("postgresql+psycopg://campocerto_app@db:5432/campocerto"))


@pytest.mark.parametrize("papel", ["Campo", "app-web", "1app", "x" * 64])
def test_nome_do_papel_simples(papel: str) -> None:
    api = f"postgresql+psycopg://{papel}:senhaDaApp2026@db:5432/campocerto"

    with pytest.raises(ConfiguracaoInvalida, match="APP_DB_USER"):
        ler_papeis(configuracao(api))


def test_papel_e_migrations_no_mesmo_banco() -> None:
    api = "postgresql+psycopg://campocerto_app:senhaDaApp2026@db:5432/outro"

    with pytest.raises(ConfiguracaoInvalida, match="mesmo banco"):
        ler_papeis(configuracao(api))


def test_sqlite_nao_tem_papel() -> None:
    with pytest.raises(ConfiguracaoInvalida, match="PostgreSQL"):
        ler_papeis(configuracao("sqlite://", None))
