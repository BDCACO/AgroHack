"""insumos e movimentacoes

Gerada por autogenerate e revisada: o downgrade original não removia o tipo
enum `tipo_movimentacao`, e um downgrade seguido de upgrade falhava com
"type already exists".

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-17 22:04:38.988425
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
        "insumo",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("categoria", sa.String(length=80), nullable=True),
        sa.Column("unidade", sa.String(length=20), nullable=False),
        sa.Column("estoque_minimo", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_insumo")),
    )
    op.create_index(
        "uq_insumo_nome_lower", "insumo", [sa.literal_column("lower(nome)")], unique=True
    )
    op.create_table(
        "movimentacao",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("insumo_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.Enum("compra", "retirada", name="tipo_movimentacao"), nullable=False),
        sa.Column("quantidade", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("validade", sa.Date(), nullable=True),
        sa.Column("observacao", sa.String(length=500), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "tipo = 'compra' OR validade IS NULL",
            name=op.f("ck_movimentacao_validade_so_em_compra"),
        ),
        sa.CheckConstraint("quantidade > 0", name=op.f("ck_movimentacao_quantidade_positiva")),
        sa.ForeignKeyConstraint(
            ["insumo_id"],
            ["insumo.id"],
            name=op.f("fk_movimentacao_insumo_id_insumo"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_movimentacao")),
    )
    op.create_index(op.f("ix_movimentacao_data"), "movimentacao", ["data"], unique=False)
    op.create_index(op.f("ix_movimentacao_insumo_id"), "movimentacao", ["insumo_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_movimentacao_insumo_id"), table_name="movimentacao")
    op.drop_index(op.f("ix_movimentacao_data"), table_name="movimentacao")
    op.drop_table("movimentacao")
    op.drop_index("uq_insumo_nome_lower", table_name="insumo")
    op.drop_table("insumo")
    sa.Enum(name="tipo_movimentacao").drop(op.get_bind(), checkfirst=True)
