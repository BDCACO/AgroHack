"""ajuste de inventário

A contagem física do galpão lança a diferença como uma movimentação com
`motivo = 'inventario'`: entrada se sobrou, saída se faltou. Como o descarte, não
conta como consumo. Só a constraint muda: a coluna `motivo` veio na 0004.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOME = "ck_movimentacoes_motivo_valido"
_ATE_0004 = "motivo IS NULL OR (motivo = 'descarte' AND tipo = 'saida')"


def upgrade() -> None:
    op.drop_constraint(op.f(_NOME), "movimentacoes", type_="check")
    op.create_check_constraint(
        op.f(_NOME), "movimentacoes", f"{_ATE_0004} OR motivo = 'inventario'"
    )


def downgrade() -> None:
    # O ajuste não cabe na regra antiga. Vira entrada ou saída comum, e não é apagado:
    # apagar mudaria o estoque sem ninguém ver.
    op.execute("UPDATE movimentacoes SET motivo = NULL WHERE motivo = 'inventario'")
    op.drop_constraint(op.f(_NOME), "movimentacoes", type_="check")
    op.create_check_constraint(op.f(_NOME), "movimentacoes", _ATE_0004)
