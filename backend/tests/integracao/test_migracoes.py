"""As migrations no PostgreSQL: descem até o zero e sobem de novo, e o schema que elas
criam é o mesmo dos modelos (o autogenerate não acha nada a fazer)."""

import subprocess

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from tests.integracao.conftest import alembic


def test_migrations_descem_e_sobem_e_batem_com_os_modelos(banco: Engine) -> None:
    # O banco da sessão pode ter preços de outro teste: descartá-los é o pedido aqui.
    alembic("-x", "descartar_precos=sim", "-x", "descartar_uuids=sim", "downgrade", "base")
    alembic("upgrade", "head")

    assert "No new upgrade operations detected" in alembic("check").stdout


def test_downgrade_nao_descarta_precos_sem_pedir(banco: Engine) -> None:
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE insumos RESTART IDENTITY CASCADE"))
        conexao.execute(
            text("INSERT INTO insumos (nome, unidade, embalagem) VALUES ('Ureia', 'kg', 50)")
        )

    with pytest.raises(subprocess.CalledProcessError) as recusa:
        alembic("downgrade", "0005")
    assert "descartar_precos=sim" in recusa.value.stderr
    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT embalagem FROM insumos")) == 50

    alembic("-x", "descartar_precos=sim", "downgrade", "0005")
    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT nome FROM insumos")) == "Ureia"
    alembic("upgrade", "head")


def test_downgrade_nao_descarta_o_uuid_do_app_sem_pedir(banco: Engine) -> None:
    identificador = "6f1c2a4e-8b3d-4f5a-9c7e-1d2b3a4c5d6e"
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE insumos RESTART IDENTITY CASCADE"))
        conexao.execute(text("INSERT INTO insumos (nome, unidade) VALUES ('Ureia', 'kg')"))
        conexao.execute(
            text(
                "INSERT INTO movimentacoes (insumo_id, tipo, data, quantidade, uuid)"
                " VALUES (1, 'entrada', '2026-10-01', 5, :uuid)"
            ),
            {"uuid": identificador},
        )

    with pytest.raises(subprocess.CalledProcessError) as recusa:
        alembic("downgrade", "0006")
    assert "descartar_uuids=sim" in recusa.value.stderr
    with banco.connect() as conexao:
        assert str(conexao.scalar(text("SELECT uuid FROM movimentacoes"))) == identificador

    alembic("-x", "descartar_uuids=sim", "downgrade", "0006")
    with banco.connect() as conexao:
        assert conexao.scalar(text("SELECT quantidade FROM movimentacoes")) == 5
    alembic("upgrade", "head")


def test_banco_recusa_o_mesmo_uuid_duas_vezes(banco: Engine) -> None:
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE insumos RESTART IDENTITY CASCADE"))
        conexao.execute(text("INSERT INTO insumos (nome, unidade) VALUES ('Ureia', 'kg')"))
    inserir = text(
        "INSERT INTO movimentacoes (insumo_id, tipo, data, quantidade, uuid)"
        " VALUES (1, 'saida', '2026-10-01', 1, '6f1c2a4e-8b3d-4f5a-9c7e-1d2b3a4c5d6e')"
    )
    with banco.begin() as conexao:
        conexao.execute(inserir)

    with pytest.raises(IntegrityError, match="uq_movimentacoes_uuid"), banco.begin() as conexao:
        conexao.execute(inserir)


@pytest.mark.parametrize(
    ("tipo", "motivo", "validade", "valor"),
    [
        ("entrada", "descarte", None, None),  # descarte é saída
        ("saida", "perdi", None, None),  # motivo desconhecido
        ("saida", None, "2027-01-01", None),  # validade só em entrada
        ("troca", None, None, None),  # tipo desconhecido
        ("saida", None, None, 3),  # preço é de compra
        ("entrada", "inventario", None, 3),  # a sobra da contagem não foi comprada
        ("entrada", None, None, 0),  # preço zero não é preço
    ],
)
def test_banco_recusa_movimentacao_incoerente_mesmo_fora_da_api(
    banco: Engine, tipo: str, motivo: str | None, validade: str | None, valor: float | None
) -> None:
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE insumos RESTART IDENTITY CASCADE"))
        conexao.execute(text("INSERT INTO insumos (nome, unidade) VALUES ('Ureia', 'kg')"))

    with pytest.raises(IntegrityError, match="ck_movimentacoes"), banco.begin() as conexao:
        conexao.execute(
            text(
                "INSERT INTO movimentacoes"
                " (insumo_id, tipo, data, quantidade, motivo, validade, valor_unitario)"
                " VALUES (1, :tipo, '2026-10-01', 1, :motivo, :validade, :valor)"
            ),
            {"tipo": tipo, "motivo": motivo, "validade": validade, "valor": valor},
        )
