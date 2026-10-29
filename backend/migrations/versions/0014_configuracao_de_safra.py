"""calendário de safra da fazenda

Tabela `configuracoes`, de uma linha só (a fazenda inteira): `meses_de_safra` (1 a 12),
vazio enquanto ninguém configurou — o motor de análise então ignora sazonalidade, como
sempre ignorou.

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
    op.create_table(
        "configuracoes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meses_de_safra", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_configuracoes")),
    )


def downgrade() -> None:
    op.drop_table("configuracoes")
