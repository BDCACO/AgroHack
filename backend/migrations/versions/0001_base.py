"""base: marco zero do schema

Sem tabelas ainda — o modelo de estoque entra quando o formato dos dados da
organização for conhecido. Esta revisão existe para que `alembic upgrade head`
crie a `alembic_version` e prove a cadeia API → Alembic → PostgreSQL desde já.

Revision ID: 0001
Revises:
Create Date: 2026-10-17
"""

from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
