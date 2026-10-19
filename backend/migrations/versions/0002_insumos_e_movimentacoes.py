"""insumos e movimentações

O estoque atual não tem coluna: é a soma das movimentações. Lote = entrada com
validade. Gerada pelo autogenerate e revisada.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "insumos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("unidade", sa.String(length=20), nullable=False),
        sa.Column(
            "estoque_minimo", sa.Numeric(precision=12, scale=3, asdecimal=False), nullable=True
        ),
        sa.Column("prazo_reposicao_dias", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "estoque_minimo >= 0", name=op.f("ck_insumos_estoque_minimo_nao_negativo")
        ),
        sa.CheckConstraint("prazo_reposicao_dias >= 0", name=op.f("ck_insumos_prazo_nao_negativo")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_insumos")),
        sa.UniqueConstraint("nome", name=op.f("uq_insumos_nome")),
    )
    op.create_table(
        "movimentacoes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("insumo_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=7), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("quantidade", sa.Numeric(precision=12, scale=3, asdecimal=False), nullable=False),
        sa.Column("validade", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "tipo IN ('entrada', 'saida')", name=op.f("ck_movimentacoes_tipo_valido")
        ),
        sa.CheckConstraint(
            "validade IS NULL OR tipo = 'entrada'",
            name=op.f("ck_movimentacoes_validade_so_em_entrada"),
        ),
        sa.CheckConstraint("quantidade > 0", name=op.f("ck_movimentacoes_quantidade_positiva")),
        sa.ForeignKeyConstraint(
            ["insumo_id"],
            ["insumos.id"],
            name=op.f("fk_movimentacoes_insumo_id_insumos"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_movimentacoes")),
    )
    op.create_index(
        op.f("ix_movimentacoes_insumo_id"), "movimentacoes", ["insumo_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_movimentacoes_insumo_id"), table_name="movimentacoes")
    op.drop_table("movimentacoes")
    op.drop_table("insumos")
