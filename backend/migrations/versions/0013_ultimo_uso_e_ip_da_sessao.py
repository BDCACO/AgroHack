"""último uso e IP do login de cada sessão

`sessoes.ultimo_uso_em`: quando a sessão foi usada pela última vez (anotado de tempos em
tempos, não a cada pedido), para cada um ver em que aparelho há login em uso e para a
validade se renovar com o uso. As sessões que já existem começam com o último uso no
momento do login, que é o único uso que se sabe delas. `sessoes.ip`: o IP do login, pelo
mesmo critério da auditoria; vazio nas que já existem, porque ninguém o anotou.

O downgrade só tira as duas colunas, sem pedir confirmação: não são dado do produtor,
são anotações sobre as sessões, que continuam valendo (a versão anterior lê a validade de
`expira_em`, que fica). A validade já renovada por esta versão fica como está, dentro do
teto de 90 dias desde o login.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Vazia primeiro, preenchida com o login, e só então obrigatória: a tabela já tem
    # sessões abertas, e um valor padrão fixo (now()) diria que todas foram usadas agora.
    op.add_column("sessoes", sa.Column("ultimo_uso_em", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE sessoes SET ultimo_uso_em = criada_em")
    op.alter_column("sessoes", "ultimo_uso_em", nullable=False)
    op.add_column("sessoes", sa.Column("ip", sa.String(length=45), nullable=True))


def downgrade() -> None:
    op.drop_column("sessoes", "ip")
    op.drop_column("sessoes", "ultimo_uso_em")
