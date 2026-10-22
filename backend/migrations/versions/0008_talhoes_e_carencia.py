"""talhões

`talhoes`: onde os insumos são aplicados (nome único, área em hectares, cultura). Tudo
opcional para o que já existe: sem talhão, o CampoCerto funciona como antes.

O downgrade apagaria os talhões, que a versão anterior não tem onde guardar. Por isso ele
se recusa enquanto houver algum, a não ser que se peça com todas as letras:

    alembic -x descartar_talhoes=sim downgrade 0007

Antes, baixe o relatório: a aba Talhões leva o cadastro.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "talhoes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("area_ha", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("cultura", sa.String(length=60), nullable=True),
        sa.Column("demonstracao", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.CheckConstraint("area_ha > 0", name=op.f("ck_talhoes_area_positiva")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_talhoes")),
        sa.UniqueConstraint("nome", name=op.f("uq_talhoes_nome")),
    )


def downgrade() -> None:
    gravados = op.get_bind().scalar(sa.text("SELECT count(*) FROM talhoes"))
    descartar = context.get_x_argument(as_dictionary=True).get("descartar_talhoes") == "sim"
    if gravados and not descartar:
        raise RuntimeError(
            f"Há {gravados} talhões cadastrados, que a versão anterior não tem onde guardar. "
            "Baixe o relatório (a aba Talhões leva o cadastro) e, para descartá-los, rode: "
            "alembic -x descartar_talhoes=sim downgrade 0007"
        )
    op.drop_table("talhoes")
