"""identificador do lançamento gerado pelo app (uuid)

`movimentacoes.uuid`, único e opcional: o app gera um para cada lançamento feito no campo,
sem sinal, e o reenvio da fila é reconhecido por ele em vez de virar duplicata. O que veio
do site, da importação e da contagem do galpão fica sem.

O downgrade apagaria os identificadores, e um lançamento ainda na fila de algum celular,
reenviado depois, seria gravado de novo. Por isso ele se recusa enquanto houver algum
gravado, a não ser que se peça com todas as letras (com os celulares já sincronizados):

    alembic -x descartar_uuids=sim downgrade 0006

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("movimentacoes", sa.Column("uuid", sa.Uuid(), nullable=True))
    # Restrição, e não só índice: dois envios simultâneos do mesmo lançamento são barrados
    # pelo banco, e a API responde com o que já está gravado.
    op.create_unique_constraint(op.f("uq_movimentacoes_uuid"), "movimentacoes", ["uuid"])


def downgrade() -> None:
    gravados = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM movimentacoes WHERE uuid IS NOT NULL")
    )
    descartar = context.get_x_argument(as_dictionary=True).get("descartar_uuids") == "sim"
    if gravados and not descartar:
        raise RuntimeError(
            f"Há {gravados} lançamentos com o identificador do app, que a versão anterior "
            "não tem onde guardar: sem ele, um lançamento reenviado por um celular seria "
            "gravado de novo. Sincronize os celulares e, para descartá-los, rode: "
            "alembic -x descartar_uuids=sim downgrade 0006"
        )
    op.drop_constraint(op.f("uq_movimentacoes_uuid"), "movimentacoes", type_="unique")
    op.drop_column("movimentacoes", "uuid")
