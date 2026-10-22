"""talhões, aplicações e carência

`talhoes`: onde os insumos são aplicados (nome único, área em hectares, cultura); e
`movimentacoes.talhao_id`, o talhão de uma retirada para uso (RESTRICT: o talhão com
aplicação não se apaga); e `insumos.carencia_dias`, os dias mínimos entre aplicar o
insumo e colher ou abater. Tudo opcional para o que já existe: sem talhão, o CampoCerto
funciona como antes.

O downgrade apagaria os talhões, o registro de onde cada insumo foi aplicado e as
carências, que a versão anterior não tem onde guardar. Por isso ele se recusa enquanto
houver algum talhão ou carência, a não ser que se peça com todas as letras:

    alembic -x descartar_talhoes=sim downgrade 0007

Antes, baixe o relatório: a aba Talhões leva o cadastro dos talhões, e a Movimentações, o
talhão de cada aplicação.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "talhoes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("area_ha", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("cultura", sa.String(length=60), nullable=True),
        sa.Column("demonstracao", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.CheckConstraint("area_ha > 0", name=op.f("ck_talhoes_area_positiva")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_talhoes")),
        sa.UniqueConstraint("nome", name=op.f("uq_talhoes_nome")),
    )
    op.add_column("movimentacoes", sa.Column("talhao_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_movimentacoes_talhao_id_talhoes"),
        "movimentacoes",
        "talhoes",
        ["talhao_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_movimentacoes_talhao_id"), "movimentacoes", ["talhao_id"])
    op.create_check_constraint(
        op.f("ck_movimentacoes_talhao_so_em_aplicacao"),
        "movimentacoes",
        "talhao_id IS NULL OR (tipo = 'saida' AND motivo IS NULL)",
    )
    op.add_column("insumos", sa.Column("carencia_dias", sa.Integer(), nullable=True))
    op.create_check_constraint(
        op.f("ck_insumos_carencia_nao_negativa"), "insumos", "carencia_dias >= 0"
    )


def downgrade() -> None:
    gravados = op.get_bind().scalar(
        sa.text(
            "SELECT (SELECT count(*) FROM talhoes)"
            " + (SELECT count(*) FROM insumos WHERE carencia_dias IS NOT NULL)"
        )
    )
    descartar = context.get_x_argument(as_dictionary=True).get("descartar_talhoes") == "sim"
    if gravados and not descartar:
        raise RuntimeError(
            f"Há {gravados} talhões ou carências cadastrados, que a versão anterior não tem onde "
            "guardar. Baixe o relatório (a aba Talhões leva o cadastro dos talhões) e, para "
            "descartá-los, rode: "
            "alembic -x descartar_talhoes=sim downgrade 0007"
        )
    op.drop_constraint(op.f("ck_insumos_carencia_nao_negativa"), "insumos", type_="check")
    op.drop_column("insumos", "carencia_dias")
    op.drop_constraint(
        op.f("ck_movimentacoes_talhao_so_em_aplicacao"), "movimentacoes", type_="check"
    )
    op.drop_index(op.f("ix_movimentacoes_talhao_id"), table_name="movimentacoes")
    op.drop_constraint(
        op.f("fk_movimentacoes_talhao_id_talhoes"), "movimentacoes", type_="foreignkey"
    )
    op.drop_column("movimentacoes", "talhao_id")
    op.drop_table("talhoes")
