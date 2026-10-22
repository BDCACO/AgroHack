"""As migrations no PostgreSQL: descem até o zero e sobem de novo, e o schema que elas
criam é o mesmo dos modelos (o autogenerate não acha nada a fazer)."""

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from tests.integracao.conftest import alembic


def test_migrations_descem_e_sobem_e_batem_com_os_modelos(banco: Engine) -> None:
    alembic("downgrade", "base")
    alembic("upgrade", "head")

    assert "No new upgrade operations detected" in alembic("check").stdout


@pytest.mark.parametrize(
    ("tipo", "motivo", "validade"),
    [
        ("entrada", "descarte", None),  # descarte é saída
        ("saida", "perdi", None),  # motivo desconhecido
        ("saida", None, "2027-01-01"),  # validade só em entrada
        ("troca", None, None),  # tipo desconhecido
    ],
)
def test_banco_recusa_movimentacao_incoerente_mesmo_fora_da_api(
    banco: Engine, tipo: str, motivo: str | None, validade: str | None
) -> None:
    with banco.begin() as conexao:
        conexao.execute(text("TRUNCATE insumos RESTART IDENTITY CASCADE"))
        conexao.execute(text("INSERT INTO insumos (nome, unidade) VALUES ('Ureia', 'kg')"))

    with pytest.raises(IntegrityError, match="ck_movimentacoes"), banco.begin() as conexao:
        conexao.execute(
            text(
                "INSERT INTO movimentacoes (insumo_id, tipo, data, quantidade, motivo, validade)"
                " VALUES (1, :tipo, '2026-10-01', 1, :motivo, :validade)"
            ),
            {"tipo": tipo, "motivo": motivo, "validade": validade},
        )
