"""usuários, sessões e quem lançou cada movimentação

`usuarios` (o dono e os funcionários: login único em minúsculas, hash scrypt da senha,
papel, ativo, e as falhas seguidas e o bloqueio contra adivinhação de senha); `sessoes`
(cada login aberto, com o SHA-256 do token, nunca o token); e `movimentacoes.usuario_id`,
quem lançou (RESTRICT: usuário não se apaga, desativa). Tudo opcional para o que já
existe: com a autenticação desligada, o CampoCerto funciona como antes.

O downgrade apagaria os usuários e o registro de quem lançou cada movimentação, que a
versão anterior não tem onde guardar. Por isso ele se recusa enquanto houver algum
usuário, a não ser que se peça com todas as letras:

    alembic -x descartar_usuarios=sim downgrade 0008

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("login", sa.String(length=40), nullable=False),
        sa.Column("senha_hash", sa.String(length=255), nullable=False),
        sa.Column("papel", sa.String(length=11), nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("falhas_seguidas", sa.Integer(), server_default="0", nullable=False),
        sa.Column("bloqueado_ate", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "papel IN ('dono', 'funcionario')", name=op.f("ck_usuarios_papel_valido")
        ),
        sa.CheckConstraint("login = lower(login)", name=op.f("ck_usuarios_login_minusculo")),
        sa.CheckConstraint("falhas_seguidas >= 0", name=op.f("ck_usuarios_falhas_nao_negativas")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usuarios")),
        sa.UniqueConstraint("login", name=op.f("uq_usuarios_login")),
    )
    op.create_table(
        "sessoes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revogada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispositivo", sa.String(length=120), nullable=True),
        sa.CheckConstraint(
            "expira_em > criada_em", name=op.f("ck_sessoes_expira_depois_de_criada")
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name=op.f("fk_sessoes_usuario_id_usuarios"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessoes")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessoes_token_hash")),
    )
    op.create_index(op.f("ix_sessoes_usuario_id"), "sessoes", ["usuario_id"])
    op.add_column("movimentacoes", sa.Column("usuario_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_movimentacoes_usuario_id_usuarios"),
        "movimentacoes",
        "usuarios",
        ["usuario_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_movimentacoes_usuario_id"), "movimentacoes", ["usuario_id"])


def downgrade() -> None:
    gravados = op.get_bind().scalar(sa.text("SELECT count(*) FROM usuarios"))
    descartar = context.get_x_argument(as_dictionary=True).get("descartar_usuarios") == "sim"
    if gravados and not descartar:
        raise RuntimeError(
            f"Há {gravados} usuários cadastrados, que a versão anterior não tem onde guardar "
            "(nem quem lançou cada movimentação). Sem eles, a API volta a ficar aberta a "
            "quem alcança a rede. Para descartá-los, rode: "
            "alembic -x descartar_usuarios=sim downgrade 0008"
        )
    op.drop_index(op.f("ix_movimentacoes_usuario_id"), table_name="movimentacoes")
    op.drop_constraint(
        op.f("fk_movimentacoes_usuario_id_usuarios"), "movimentacoes", type_="foreignkey"
    )
    op.drop_column("movimentacoes", "usuario_id")
    op.drop_index(op.f("ix_sessoes_usuario_id"), table_name="sessoes")
    op.drop_table("sessoes")
    op.drop_table("usuarios")
