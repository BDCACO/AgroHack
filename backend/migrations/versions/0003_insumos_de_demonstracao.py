"""insumos de demonstração

Marca os insumos gerados por `python -m app.demo`, para a tela avisar e para o
`limpar` apagar só eles. O default é `sa.false()`, não o `text('0')` que o
autogenerate escreve a partir do SQLite: no PostgreSQL, 0 não é booleano.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "insumos",
        sa.Column("demonstracao", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("insumos", "demonstracao")
