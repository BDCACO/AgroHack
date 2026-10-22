"""preço da compra, embalagem e pedido mínimo

`movimentacoes.valor_unitario` (R$ por unidade, só em compra: entrada sem motivo) e,
em `insumos`, `embalagem` e `pedido_minimo`. Tudo opcional: sem eles, o CampoCerto
funciona como antes, só não fala em reais nem arredonda a reposição em embalagens.

O downgrade apagaria os preços e as embalagens, porque não há onde guardá-los na
versão anterior. Por isso ele se recusa enquanto houver algum gravado, a não ser que
se peça com todas as letras:

    alembic -x descartar_precos=sim downgrade 0005

Antes, baixe o relatório: a aba Movimentações leva os preços.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "movimentacoes",
        sa.Column("valor_unitario", sa.Numeric(precision=14, scale=4), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_movimentacoes_valor_unitario_positivo"), "movimentacoes", "valor_unitario > 0"
    )
    op.create_check_constraint(
        op.f("ck_movimentacoes_valor_so_em_compra"),
        "movimentacoes",
        "valor_unitario IS NULL OR (tipo = 'entrada' AND motivo IS NULL)",
    )
    op.add_column("insumos", sa.Column("embalagem", sa.Numeric(precision=12, scale=3)))
    op.add_column("insumos", sa.Column("pedido_minimo", sa.Numeric(precision=12, scale=3)))
    op.create_check_constraint(op.f("ck_insumos_embalagem_positiva"), "insumos", "embalagem > 0")
    op.create_check_constraint(
        op.f("ck_insumos_pedido_minimo_nao_negativo"), "insumos", "pedido_minimo >= 0"
    )


def downgrade() -> None:
    gravados = op.get_bind().scalar(
        sa.text(
            "SELECT (SELECT count(*) FROM movimentacoes WHERE valor_unitario IS NOT NULL)"
            " + (SELECT count(*) FROM insumos"
            "    WHERE embalagem IS NOT NULL OR pedido_minimo IS NOT NULL)"
        )
    )
    descartar = context.get_x_argument(as_dictionary=True).get("descartar_precos") == "sim"
    if gravados and not descartar:
        raise RuntimeError(
            f"Há {gravados} registros com preço, embalagem ou pedido mínimo, que a versão "
            "anterior não tem onde guardar. Baixe o relatório (a aba Movimentações leva os "
            "preços) e, para descartá-los, rode: "
            "alembic -x descartar_precos=sim downgrade 0005"
        )
    op.drop_constraint(op.f("ck_insumos_pedido_minimo_nao_negativo"), "insumos", type_="check")
    op.drop_constraint(op.f("ck_insumos_embalagem_positiva"), "insumos", type_="check")
    op.drop_column("insumos", "pedido_minimo")
    op.drop_column("insumos", "embalagem")
    op.drop_constraint(op.f("ck_movimentacoes_valor_so_em_compra"), "movimentacoes", type_="check")
    op.drop_constraint(
        op.f("ck_movimentacoes_valor_unitario_positivo"), "movimentacoes", type_="check"
    )
    op.drop_column("movimentacoes", "valor_unitario")
