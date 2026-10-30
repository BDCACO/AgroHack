"""marcas preferenciais do insumo

`insumos.marcas_preferenciais`: texto livre com as marcas ou especificações aceitas na
compra ("Yara, Heringer"), opcional. Entra na mensagem de cotação para a revenda saber o
que pode e o que não pode mandar.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("insumos", sa.Column("marcas_preferenciais", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("insumos", "marcas_preferenciais")
