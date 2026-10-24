"""O papel da aplicação e os tempos-limite, no PostgreSQL de verdade.

A API conecta com um papel que lê e grava dados e só (app/papel_da_aplicacao.py): aqui se
prova que ele não derruba, esvazia nem altera tabela, não cria nada e não roda comando no
servidor; que a tabela de uma migration futura nasce com as permissões dele; que a consulta
demorada e a espera por trava desistem, e a API responde 503 com Retry-After; que as
migrations não herdam esses limites; e que a API de produção não sobe com o dono."""

import os
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import Connection, Engine, create_engine, make_url, text
from sqlalchemy.exc import DBAPIError, OperationalError, ProgrammingError

from app.core import senha
from app.core.config import Settings
from app.core.database import argumentos_do_engine, problemas_do_papel
from app.core.relogio import hoje
from tests.integracao.conftest import (
    BACKEND,
    PAPEL_DA_APP,
    URL_DA_APP,
    URL_DO_BANCO,
    alembic,
    subir_uvicorn,
)

SENHA_DA_MARIA = "dona-maria-2026"


def engine_da_app(**tempos: int) -> Engine:
    """Um engine como o da API (app/core/database.py), com o papel da aplicação."""
    return create_engine(
        URL_DA_APP,
        **argumentos_do_engine(Settings(environment="test", database_url=URL_DA_APP, **tempos)),
    )


@pytest.fixture
def app_no_banco(banco: Engine) -> Iterator[Connection]:
    """Uma conexão com o papel da aplicação; o que ela fizer é desfeito no fim."""
    engine = engine_da_app()
    with engine.connect() as conexao:
        yield conexao
        conexao.rollback()
    engine.dispose()


def test_a_api_conecta_com_o_papel_da_aplicacao_sem_poderes(app_no_banco: Connection) -> None:
    assert app_no_banco.scalar(text("SELECT current_user")) == PAPEL_DA_APP
    assert not app_no_banco.scalar(
        text("SELECT rolsuper FROM pg_roles WHERE rolname = :p"), {"p": PAPEL_DA_APP}
    )
    assert problemas_do_papel(app_no_banco.engine) == []


@pytest.mark.parametrize(
    "comando",
    [
        "DROP TABLE movimentacoes",
        "TRUNCATE insumos CASCADE",
        "ALTER TABLE insumos ADD COLUMN intrusa integer",
        "ALTER TABLE insumos OWNER TO CURRENT_USER",
        "CREATE TABLE intrusa (id integer)",
        "CREATE INDEX ix_intruso ON insumos (nome)",
        "CREATE SCHEMA intruso",
        "COPY (SELECT 1) TO PROGRAM 'id'",
        "SELECT pg_read_file('/etc/passwd')",
        "ALTER ROLE CURRENT_USER SUPERUSER",
        "CREATE ROLE intruso",
        "UPDATE alembic_version SET version_num = '0001'",
        "DELETE FROM alembic_version",
    ],
)
def test_o_papel_da_aplicacao_nao_tem_poder_de_dono(app_no_banco: Connection, comando: str) -> None:
    with pytest.raises(ProgrammingError) as recusa:
        app_no_banco.execute(text(comando))

    assert recusa.value.orig.sqlstate == "42501"  # insufficient_privilege


def test_o_papel_da_aplicacao_le_e_grava_dados(app_no_banco: Connection) -> None:
    categoria = app_no_banco.scalar(
        text("INSERT INTO categorias (nome) VALUES ('Teste de permissão') RETURNING id")
    )
    app_no_banco.execute(
        text("UPDATE categorias SET nome = 'Teste de permissão 2' WHERE id = :id"),
        {"id": categoria},
    )
    assert app_no_banco.scalar(
        text("SELECT nome FROM categorias WHERE id = :id"), {"id": categoria}
    ) == ("Teste de permissão 2")
    app_no_banco.execute(text("DELETE FROM categorias WHERE id = :id"), {"id": categoria})
    # A revisão do schema ele lê (para conferir, um dia, se o banco está em dia); gravar, não.
    assert app_no_banco.scalar(text("SELECT version_num FROM alembic_version"))


def test_tabela_de_migration_futura_nasce_com_as_permissoes(banco: Engine) -> None:
    """O papel já existe e o comando não roda de novo (um `make migrate` com a API no ar):
    a tabela que o dono cria ganha as permissões sozinha, pelo ALTER DEFAULT PRIVILEGES."""
    with banco.begin() as conexao:
        conexao.execute(text("CREATE TABLE migration_futura (id serial PRIMARY KEY, nome text)"))
    try:
        engine = engine_da_app()
        with engine.begin() as conexao:
            conexao.execute(text("INSERT INTO migration_futura (nome) VALUES ('nova')"))
            assert conexao.scalar(text("SELECT nome FROM migration_futura")) == "nova"
        with pytest.raises(ProgrammingError), engine.begin() as conexao:
            conexao.execute(text("DROP TABLE migration_futura"))
        engine.dispose()
    finally:
        with banco.begin() as conexao:
            conexao.execute(text("DROP TABLE migration_futura"))


def test_a_conexao_da_api_leva_os_tempos_limite(app_no_banco: Connection) -> None:
    def mostrar(nome: str) -> str:
        return app_no_banco.scalar(text(f"SHOW {nome}"))

    assert mostrar("statement_timeout") == "30s"
    assert mostrar("lock_timeout") == "5s"
    assert mostrar("idle_in_transaction_session_timeout") == "1min"


def test_consulta_que_passa_do_limite_e_cortada(banco: Engine) -> None:
    engine = engine_da_app(db_statement_timeout_ms=200)
    comeco = time.perf_counter()

    with pytest.raises(OperationalError) as corte, engine.connect() as conexao:
        conexao.execute(text("SELECT pg_sleep(5)"))

    assert corte.value.orig.sqlstate == "57014"  # query_canceled
    assert time.perf_counter() - comeco < 3
    engine.dispose()


def test_transacao_esquecida_aberta_e_derrubada(banco: Engine) -> None:
    engine = engine_da_app(db_idle_in_transaction_timeout_ms=300)
    with engine.connect() as conexao:
        conexao.execute(text("SELECT 1"))  # abre a transação e a esquece
        time.sleep(1)
        with pytest.raises(DBAPIError) as derrubada:
            conexao.execute(text("SELECT 1"))
    # Erro do servidor, e não 503: transação parada um minuto dentro da API é defeito.
    assert derrubada.value.orig.sqlstate == "25P03"  # idle_in_transaction_session_timeout
    engine.dispose()


@pytest.fixture
def maria(banco: Engine) -> None:
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE usuarios RESTART IDENTITY CASCADE"))
        conexao.execute(
            text(
                "INSERT INTO usuarios (nome, login, senha_hash, papel, ativo, criado_em,"
                " falhas_seguidas) VALUES ('Dona Maria', 'maria', :hash, 'dono', true, now(), 0)"
            ),
            {"hash": senha.gerar_hash(SENHA_DA_MARIA)},
        )


def segurar(
    banco: Engine, consulta: str, enquanto: threading.Event, **parametros: object
) -> threading.Thread:
    """Outra conexão (o dono) segura a trava da consulta até `enquanto` ser marcado."""
    pronta = threading.Event()

    def segurar_a_trava() -> None:
        with banco.begin() as conexao:
            conexao.execute(text(consulta), parametros)
            pronta.set()
            enquanto.wait(30)

    linha = threading.Thread(target=segurar_a_trava)
    linha.start()
    assert pronta.wait(10)
    return linha


def entrar(base: str) -> httpx.Response:
    return httpx.post(
        f"{base}/auth/entrar", json={"login": "maria", "senha": SENHA_DA_MARIA}, timeout=60
    )


def test_login_esperando_trava_desiste_e_responde_503(
    api: httpx.Client, servidor: str, banco: Engine, maria: None
) -> None:
    """O login trava a linha do usuário (FOR UPDATE). Com ela presa por outra conexão, a API
    desiste no lock_timeout padrão (5 s) e diz para tentar de novo, em vez de pendurar."""
    soltar = threading.Event()
    linha = segurar(banco, "SELECT 1 FROM usuarios WHERE login = 'maria' FOR UPDATE", soltar)
    try:
        comeco = time.perf_counter()
        resposta = entrar(servidor)
        demora = time.perf_counter() - comeco
    finally:
        soltar.set()
        linha.join()

    assert resposta.status_code == 503, resposta.text
    assert resposta.headers["Retry-After"] == "5"
    assert "Outro pedido está mexendo nos mesmos dados" in resposta.json()["detail"]
    assert 4 < demora < 15
    # Solta a trava, o mesmo login entra.
    assert entrar(servidor).status_code == 200


def test_consulta_demorada_na_api_responde_503(banco: Engine, maria: None) -> None:
    """Com o statement_timeout menor que a espera pela trava, é ele que corta: a outra
    frase, o mesmo 503."""
    for base in subir_uvicorn(
        AUTENTICACAO="false", DB_STATEMENT_TIMEOUT_MS="500", DB_LOCK_TIMEOUT_MS="20000"
    ):
        soltar = threading.Event()
        linha = segurar(banco, "SELECT 1 FROM usuarios WHERE login = 'maria' FOR UPDATE", soltar)
        try:
            resposta = entrar(base)
        finally:
            soltar.set()
            linha.join()

        assert resposta.status_code == 503, resposta.text
        assert resposta.headers["Retry-After"] == "5"
        assert "demorou demais" in resposta.json()["detail"]


def test_lote_do_app_que_espera_trava_para_e_o_reenvio_completa(
    api: httpx.Client, banco: Engine
) -> None:
    """O segundo item espera a trava do insumo (outra conexão o segura) e estoura: o lote
    responde 503, o primeiro item fica gravado, e o reenvio do mesmo lote completa sem
    duplicar nada."""
    ureia = api.post("/insumos", json={"nome": "Ureia", "unidade": "kg"}).json()["id"]
    sal = api.post("/insumos", json={"nome": "Sal mineral", "unidade": "kg"}).json()["id"]
    lote = {
        "movimentacoes": [
            {
                "uuid": str(uuid4()),
                "insumo_id": insumo,
                "tipo": "entrada",
                "data": str(hoje() - timedelta(days=1)),
                "quantidade": 10,
            }
            for insumo in (ureia, sal)
        ]
    }
    soltar = threading.Event()
    linha = segurar(banco, "SELECT 1 FROM insumos WHERE id = :id FOR UPDATE", soltar, id=sal)
    try:
        resposta = api.post("/movimentacoes/lote", json=lote)
    finally:
        soltar.set()
        linha.join()

    assert resposta.status_code == 503, resposta.text
    assert resposta.headers["Retry-After"] == "5"
    reenvio = api.post("/movimentacoes/lote", json=lote)
    assert reenvio.status_code == 200, reenvio.text
    assert [r["situacao"] for r in reenvio.json()["resultados"]] == ["ja_existia", "gravada"]
    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT count(*) FROM movimentacoes")) == 2


def test_migrations_nao_herdam_os_tempos_limite_da_api(banco: Engine) -> None:
    """A migration espera a trava que precisar, por mais que a API tenha limites curtos:
    com os da API (1 ms), ela desistiria na hora."""
    alembic("-x", "descartar_categorias=sim", "downgrade", "0010")
    soltar = threading.Event()
    # A 0011 altera a tabela de insumos: espera quem a está lendo.
    linha = segurar(banco, "LOCK TABLE insumos IN ACCESS SHARE MODE", soltar)
    try:
        migracao = subprocess.Popen(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND,
            env=os.environ
            | {
                "ENVIRONMENT": "test",
                "DATABASE_URL": URL_DA_APP,
                "MIGRATIONS_DATABASE_URL": URL_DO_BANCO,
                "DB_STATEMENT_TIMEOUT_MS": "1",
                "DB_LOCK_TIMEOUT_MS": "1",
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        with banco.connect() as conexao:
            for _ in range(100):
                esperando = conexao.scalar(text("SELECT count(*) FROM pg_locks WHERE NOT granted"))
                if esperando:
                    break
                time.sleep(0.1)
        assert esperando, "a migration não chegou a esperar a trava"
        time.sleep(1)  # bem mais que os limites da API
        assert migracao.poll() is None
    finally:
        soltar.set()
        linha.join()
    _, erros = migracao.communicate(timeout=60)
    assert migracao.returncode == 0, erros


def uvicorn_de_producao(url: str) -> subprocess.CompletedProcess[str]:
    ambiente = os.environ | {
        "ENVIRONMENT": "production",
        "AUTENTICACAO": "true",
        "DATABASE_URL": url,
    }
    ambiente.pop("MIGRATIONS_DATABASE_URL", None)
    return subprocess.run(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "0"],
        cwd=BACKEND,
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_producao_conectada_como_superusuario_nao_sobe(banco: Engine) -> None:
    processo = uvicorn_de_producao(URL_DO_BANCO)

    assert processo.returncode != 0
    assert "é superusuário" in processo.stderr
    assert "MIGRATIONS_DATABASE_URL" in processo.stderr


def test_producao_conectada_como_dona_das_tabelas_nao_sobe(banco: Engine) -> None:
    """Sem ser superusuário, o dono das tabelas ainda as derruba e altera."""
    papel, senha_do_papel = "campocerto_dono_teste", "senhaDoDonoDeTeste1"
    with banco.begin() as conexao:
        conexao.execute(text(f"DROP ROLE IF EXISTS {papel}"))
        conexao.execute(text(f"CREATE ROLE {papel} LOGIN PASSWORD '{senha_do_papel}'"))
        conexao.execute(text("CREATE TABLE tabela_do_dono (id integer)"))
        conexao.execute(text(f"ALTER TABLE tabela_do_dono OWNER TO {papel}"))
    try:
        url = make_url(URL_DO_BANCO).set(username=papel, password=senha_do_papel)
        processo = uvicorn_de_producao(url.render_as_string(hide_password=False))
    finally:
        with banco.begin() as conexao:
            conexao.execute(text("DROP TABLE tabela_do_dono"))
            conexao.execute(text(f"DROP ROLE {papel}"))

    assert processo.returncode != 0
    assert "é dono (ou membro do dono) de tabelas" in processo.stderr
    assert "é superusuário" not in processo.stderr
