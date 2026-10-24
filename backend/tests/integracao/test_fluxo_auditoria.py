"""A trilha de auditoria no PostgreSQL de verdade: a API conectada com o papel da aplicação
só acrescenta e lê eventos, e nem o dono os altera ou apaga sem querer."""

from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from tests.integracao.conftest import URL_DA_APP, garantir_o_papel_da_aplicacao


@pytest.fixture
def evento_gravado(banco: Engine) -> int:
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE eventos_de_auditoria RESTART IDENTITY"))
        return conexao.scalar(
            text(
                "INSERT INTO eventos_de_auditoria (acao, entidade, entidade_id, dados, origem)"
                " VALUES ('insumo.removido', 'insumo', 1, CAST(:dados AS jsonb), 'terminal')"
                " RETURNING id"
            ),
            {"dados": '{"nome": "Ureia"}'},
        )


@pytest.fixture
def app_no_banco(banco: Engine) -> Iterator[Connection]:
    """Uma conexão com o papel da aplicação, a da API; o que ela fizer é desfeito no fim."""
    engine = create_engine(URL_DA_APP)
    with engine.connect() as conexao:
        yield conexao
        conexao.rollback()
    engine.dispose()


@pytest.mark.parametrize(
    "comando",
    [
        "UPDATE eventos_de_auditoria SET dados = '{}'",
        "UPDATE eventos_de_auditoria SET acao = 'demo.limpa' WHERE id = 1",
        "DELETE FROM eventos_de_auditoria",
        "DELETE FROM eventos_de_auditoria WHERE id = 1",
        "TRUNCATE eventos_de_auditoria",
    ],
)
def test_o_papel_da_aplicacao_nao_altera_nem_apaga_evento(
    evento_gravado: int, app_no_banco: Connection, comando: str
) -> None:
    with pytest.raises(ProgrammingError) as recusa:
        app_no_banco.execute(text(comando))

    assert recusa.value.orig.sqlstate == "42501"  # insufficient_privilege
    app_no_banco.rollback()
    assert app_no_banco.scalar(text("SELECT dados->>'nome' FROM eventos_de_auditoria")) == "Ureia"


def test_o_papel_da_aplicacao_acrescenta_e_le(
    evento_gravado: int, app_no_banco: Connection
) -> None:
    app_no_banco.execute(
        text(
            "INSERT INTO eventos_de_auditoria (acao, dados, origem)"
            " VALUES ('demo.limpa', CAST('{}' AS jsonb), 'terminal')"
        )
    )

    assert app_no_banco.scalar(text("SELECT count(*) FROM eventos_de_auditoria")) == 2


def test_o_comando_do_papel_rodado_de_novo_nao_devolve_o_delete(
    evento_gravado: int, banco: Engine
) -> None:
    """A cada subida ele refaz as permissões com um GRANT em todas as tabelas: a trilha
    tem de sair dele só com INSERT e SELECT de novo."""
    garantir_o_papel_da_aplicacao()

    engine = create_engine(URL_DA_APP)
    with pytest.raises(ProgrammingError), engine.begin() as conexao:
        conexao.execute(text("DELETE FROM eventos_de_auditoria"))
    engine.dispose()


@pytest.mark.parametrize(
    "comando",
    [
        "UPDATE eventos_de_auditoria SET dados = '{}'",
        "DELETE FROM eventos_de_auditoria",
    ],
)
def test_nem_o_dono_altera_ou_apaga_evento_sem_querer(
    evento_gravado: int, banco: Engine, comando: str
) -> None:
    # O DELETE à mão no psql, ou a migration que "limpa" dados, não apagam o rastro: só
    # derrubando o gatilho, o que ninguém faz por engano.
    with pytest.raises(IntegrityError, match="só aceita acrescentar"), banco.begin() as conexao:
        conexao.execute(text(comando))

    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT dados->>'nome' FROM eventos_de_auditoria")) == "Ureia"
