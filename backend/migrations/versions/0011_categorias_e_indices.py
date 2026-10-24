"""categorias de insumo

`categorias` (nome único), já com as de partida de uma propriedade de Rondônia (lavoura de
soja, milho e café, e gado de corte e de leite), e `insumos.categoria_id`, opcional
(RESTRICT: a categoria com insumo não se apaga). Sem categoria, o CampoCerto funciona
como antes.

O downgrade apagaria a categoria de cada insumo e as categorias cadastradas pelo dono, que
a versão anterior não tem onde guardar. Por isso ele se recusa enquanto houver algum
insumo com categoria ou alguma categoria além das de partida, a não ser que se peça com
todas as letras:

    alembic -x descartar_categorias=sim downgrade 0010

Antes, baixe o relatório: a aba Movimentações leva a categoria de cada insumo.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# As de partida. Corretivo à parte do fertilizante: o calcário é a maior compra de quem
# abre área em Rondônia (solo ácido), e somado ao adubo esconderia os dois. Semente e muda
# juntas: o café clonal (conilon) se planta por muda. Combustível porque o diesel do
# trator é insumo que acaba e se compra como os outros.
CATEGORIAS_DE_PARTIDA = (
    "Fertilizante",
    "Corretivo de solo",
    "Defensivo agrícola",
    "Semente e muda",
    "Medicamento veterinário",
    "Nutrição animal",
    "Combustível e lubrificante",
    "Outros",
)


def upgrade() -> None:
    categorias = op.create_table(
        "categorias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=60), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categorias")),
        sa.UniqueConstraint("nome", name=op.f("uq_categorias_nome")),
    )
    op.bulk_insert(categorias, [{"nome": nome} for nome in CATEGORIAS_DE_PARTIDA])
    op.add_column("insumos", sa.Column("categoria_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_insumos_categoria_id_categorias"),
        "insumos",
        "categorias",
        ["categoria_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    # O filtro da lista de insumos e a trava do RESTRICT ao remover a categoria.
    op.create_index(op.f("ix_insumos_categoria_id"), "insumos", ["categoria_id"])


def downgrade() -> None:
    gravados = op.get_bind().scalar(
        sa.text(
            "SELECT (SELECT count(*) FROM insumos WHERE categoria_id IS NOT NULL)"
            " + (SELECT count(*) FROM categorias WHERE nome NOT IN :de_partida)"
        ).bindparams(sa.bindparam("de_partida", CATEGORIAS_DE_PARTIDA, expanding=True))
    )
    descartar = context.get_x_argument(as_dictionary=True).get("descartar_categorias") == "sim"
    if gravados and not descartar:
        raise RuntimeError(
            f"Há {gravados} insumos com categoria ou categorias cadastradas, que a versão "
            "anterior não tem onde guardar. Baixe o relatório (a aba Movimentações leva a "
            "categoria de cada insumo) e, para descartá-las, rode: "
            "alembic -x descartar_categorias=sim downgrade 0010"
        )
    op.drop_index(op.f("ix_insumos_categoria_id"), table_name="insumos")
    op.drop_constraint(op.f("fk_insumos_categoria_id_categorias"), "insumos", type_="foreignkey")
    op.drop_column("insumos", "categoria_id")
    op.drop_table("categorias")
