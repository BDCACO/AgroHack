"""código de barras do insumo

`insumos.codigo_de_barras`: o código de fábrica da embalagem (EAN), opcional. O app
mobile ensina o vínculo na primeira leitura que não reconhece um código, e reconhece
sozinho da próxima vez. Único, para o mesmo código nunca apontar para dois insumos.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("insumos", sa.Column("codigo_de_barras", sa.String(length=64), nullable=True))
    op.create_unique_constraint(
        op.f("uq_insumos_codigo_de_barras"), "insumos", ["codigo_de_barras"]
    )


def downgrade() -> None:
    op.drop_constraint(op.f("uq_insumos_codigo_de_barras"), "insumos", type_="unique")
    op.drop_column("insumos", "codigo_de_barras")
