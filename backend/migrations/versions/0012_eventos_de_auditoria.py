"""eventos de auditoria, somente acrescentar

`eventos_de_auditoria`: o que de sensível ou destrutivo aconteceu (remover movimentação,
insumo ou talhão, confirmar importação, cancelar pedido, mexer em usuário, login recusado
e bloqueio...), quem fez, quando, de onde, e em `dados` o conteúdo do que foi apagado ou o
antes e o depois do que mudou. Com os índices da consulta (os mais recentes primeiro, por
ação, por usuário e por entidade).

Somente acrescentar, em duas camadas:

- o papel da aplicação só tem INSERT e SELECT nesta tabela. O ALTER DEFAULT PRIVILEGES do
  dono (app/papel_da_aplicacao.py) daria a ela UPDATE e DELETE ao nascer; aqui eles são
  tirados de quem os ganhou, e o comando do papel, a cada subida, também os tira;
- um gatilho recusa UPDATE e DELETE de qualquer um, o dono inclusive: o `DELETE` à mão no
  psql e a migration que "limpa" dados não apagam o rastro por engano. O dono ainda pode
  derrubar o gatilho (é dono), mas não sem querer. TRUNCATE e DROP ficam com o dono: o
  primeiro esvazia o banco descartável dos testes; o segundo é este downgrade, que pede
  confirmação.

O downgrade apagaria a trilha inteira, que a versão anterior não tem onde guardar. Por
isso ele se recusa enquanto houver algum evento, a não ser que se peça com todas as
letras:

    alembic -x descartar_auditoria=sim downgrade 0011

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eventos_de_auditoria",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "ocorrido_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("acao", sa.String(length=40), nullable=False),
        sa.Column("entidade", sa.String(length=20), nullable=True),
        sa.Column("entidade_id", sa.Integer(), nullable=True),
        sa.Column(
            "dados",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("origem", sa.String(length=8), nullable=False),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("dispositivo", sa.String(length=120), nullable=True),
        sa.CheckConstraint(
            "origem IN ('api', 'terminal')", name=op.f("ck_eventos_de_auditoria_origem_valida")
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name=op.f("fk_eventos_de_auditoria_usuario_id_usuarios"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eventos_de_auditoria")),
    )
    op.create_index(
        "ix_eventos_de_auditoria_ocorrido_em_id", "eventos_de_auditoria", ["ocorrido_em", "id"]
    )
    op.create_index(
        "ix_eventos_de_auditoria_acao_ocorrido_em_id",
        "eventos_de_auditoria",
        ["acao", "ocorrido_em", "id"],
    )
    op.create_index(
        "ix_eventos_de_auditoria_usuario_id_ocorrido_em_id",
        "eventos_de_auditoria",
        ["usuario_id", "ocorrido_em", "id"],
    )
    op.create_index(
        "ix_eventos_de_auditoria_entidade_ocorrido_em_id",
        "eventos_de_auditoria",
        ["entidade", "entidade_id", "ocorrido_em", "id"],
    )
    # O ALTER DEFAULT PRIVILEGES do dono deu a tabela nova, ao nascer, o DML inteiro ao papel
    # da aplicação. Tira o que muda e o que apaga de todo papel que não é o dono, sem
    # precisar saber o nome dele (é do ambiente, não do schema).
    op.execute(
        """
        DO $$
        DECLARE papel text;
        BEGIN
          FOR papel IN
            SELECT DISTINCT a.grantee::regrole::text
            FROM pg_class c, aclexplode(c.relacl) a
            WHERE c.oid = 'public.eventos_de_auditoria'::regclass
              AND a.grantee <> c.relowner AND a.grantee <> 0
          LOOP
            EXECUTE format(
              'REVOKE UPDATE, DELETE, TRUNCATE ON public.eventos_de_auditoria FROM %s', papel
            );
          END LOOP;
        END $$;
        """
    )
    op.execute(
        """
        CREATE FUNCTION recusar_mudanca_na_auditoria() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'A trilha de auditoria só aceita acrescentar: um evento não se '
            'altera nem se apaga.'
            USING ERRCODE = 'restrict_violation';
        END $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER somente_acrescentar
        BEFORE UPDATE OR DELETE ON eventos_de_auditoria
        FOR EACH ROW EXECUTE FUNCTION recusar_mudanca_na_auditoria();
        """
    )


def downgrade() -> None:
    gravados = op.get_bind().scalar(sa.text("SELECT count(*) FROM eventos_de_auditoria"))
    descartar = context.get_x_argument(as_dictionary=True).get("descartar_auditoria") == "sim"
    if gravados and not descartar:
        raise RuntimeError(
            f"Há {gravados} eventos de auditoria, que a versão anterior não tem onde guardar: "
            "descer apagaria o registro de quem removeu, alterou e tentou entrar. Para "
            "descartá-los, rode: alembic -x descartar_auditoria=sim downgrade 0011"
        )
    op.execute("DROP TRIGGER somente_acrescentar ON eventos_de_auditoria")
    op.execute("DROP FUNCTION recusar_mudanca_na_auditoria()")
    op.drop_index("ix_eventos_de_auditoria_entidade_ocorrido_em_id", "eventos_de_auditoria")
    op.drop_index("ix_eventos_de_auditoria_usuario_id_ocorrido_em_id", "eventos_de_auditoria")
    op.drop_index("ix_eventos_de_auditoria_acao_ocorrido_em_id", "eventos_de_auditoria")
    op.drop_index("ix_eventos_de_auditoria_ocorrido_em_id", "eventos_de_auditoria")
    op.drop_table("eventos_de_auditoria")
