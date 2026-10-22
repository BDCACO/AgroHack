"""motivo da movimentação: descarte

Saída com `motivo = 'descarte'` tira do estoque sem contar como consumo (lote vencido
jogado fora ou devolvido). Coluna à parte, e não um terceiro `tipo`, para o saldo, o
site e o app continuarem vendo uma saída. Escrita à mão: o batch_alter_table do
autogenerate só serviria ao SQLite, e os testes criam o schema pelos modelos.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("movimentacoes", sa.Column("motivo", sa.String(length=10), nullable=True))
    op.create_check_constraint(
        op.f("ck_movimentacoes_motivo_valido"),
        "movimentacoes",
        "motivo IS NULL OR (motivo = 'descarte' AND tipo = 'saida')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_movimentacoes_motivo_valido"), "movimentacoes", type_="check")
    op.drop_column("movimentacoes", "motivo")
