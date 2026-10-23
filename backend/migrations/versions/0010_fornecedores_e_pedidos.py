"""fornecedores, pedidos de compra e de quem se comprou

`fornecedores` (nome único, contato, telefone, cidade, observação, ativo); `pedidos` (a
quem, quando foi feito, a previsão de chegada, a situação e quem fez) com os
`itens_do_pedido` (insumo, quantidade, preço combinado e quanto já chegou); e, em
`movimentacoes`, `fornecedor_id` (de quem foi a compra) e `item_do_pedido_id` (o pedido que
ela recebeu), só em compra. Tudo opcional para o que já existe: sem fornecedor nem
pedido, o CampoCerto funciona como antes.

O downgrade apagaria os fornecedores, os pedidos e de quem foi cada compra, que a versão
anterior não tem onde guardar. Por isso ele se recusa enquanto houver algum fornecedor ou
pedido, a não ser que se peça com todas as letras:

    alembic -x descartar_compras=sim downgrade 0009

Antes, baixe o relatório: a aba Movimentações leva o fornecedor de cada compra, e a
Pedidos, o que ainda falta chegar.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fornecedores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("contato", sa.String(length=120), nullable=True),
        sa.Column("telefone", sa.String(length=30), nullable=True),
        sa.Column("cidade", sa.String(length=80), nullable=True),
        sa.Column("observacao", sa.String(length=500), nullable=True),
        sa.Column("ativo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("demonstracao", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fornecedores")),
        sa.UniqueConstraint("nome", name=op.f("uq_fornecedores_nome")),
    )
    op.create_table(
        "pedidos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fornecedor_id", sa.Integer(), nullable=True),
        sa.Column("situacao", sa.String(length=9), nullable=False),
        sa.Column("feito_em", sa.Date(), nullable=False),
        sa.Column("previsto_para", sa.Date(), nullable=True),
        sa.Column("observacao", sa.String(length=500), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "situacao IN ('aberto', 'parcial', 'recebido', 'cancelado')",
            name=op.f("ck_pedidos_situacao_valida"),
        ),
        sa.CheckConstraint(
            "previsto_para >= feito_em", name=op.f("ck_pedidos_previsto_depois_de_feito")
        ),
        sa.ForeignKeyConstraint(
            ["fornecedor_id"],
            ["fornecedores.id"],
            name=op.f("fk_pedidos_fornecedor_id_fornecedores"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name=op.f("fk_pedidos_usuario_id_usuarios"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pedidos")),
    )
    op.create_index(op.f("ix_pedidos_fornecedor_id"), "pedidos", ["fornecedor_id"])
    op.create_index(op.f("ix_pedidos_usuario_id"), "pedidos", ["usuario_id"])
    op.create_table(
        "itens_do_pedido",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pedido_id", sa.Integer(), nullable=False),
        sa.Column("insumo_id", sa.Integer(), nullable=False),
        sa.Column("quantidade", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("valor_unitario", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column(
            "quantidade_recebida",
            sa.Numeric(precision=12, scale=3),
            server_default="0",
            nullable=False,
        ),
        sa.CheckConstraint("quantidade > 0", name=op.f("ck_itens_do_pedido_quantidade_positiva")),
        sa.CheckConstraint(
            "valor_unitario > 0", name=op.f("ck_itens_do_pedido_valor_unitario_positivo")
        ),
        sa.CheckConstraint(
            "quantidade_recebida >= 0", name=op.f("ck_itens_do_pedido_recebida_nao_negativa")
        ),
        sa.ForeignKeyConstraint(
            ["pedido_id"],
            ["pedidos.id"],
            name=op.f("fk_itens_do_pedido_pedido_id_pedidos"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["insumo_id"],
            ["insumos.id"],
            name=op.f("fk_itens_do_pedido_insumo_id_insumos"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_itens_do_pedido")),
        sa.UniqueConstraint("pedido_id", "insumo_id", name=op.f("uq_itens_do_pedido_pedido_id")),
    )
    op.create_index(op.f("ix_itens_do_pedido_pedido_id"), "itens_do_pedido", ["pedido_id"])
    op.create_index(op.f("ix_itens_do_pedido_insumo_id"), "itens_do_pedido", ["insumo_id"])

    op.add_column("movimentacoes", sa.Column("fornecedor_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_movimentacoes_fornecedor_id_fornecedores"),
        "movimentacoes",
        "fornecedores",
        ["fornecedor_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_movimentacoes_fornecedor_id"), "movimentacoes", ["fornecedor_id"])
    op.create_check_constraint(
        op.f("ck_movimentacoes_fornecedor_so_em_compra"),
        "movimentacoes",
        "fornecedor_id IS NULL OR (tipo = 'entrada' AND motivo IS NULL)",
    )
    op.add_column("movimentacoes", sa.Column("item_do_pedido_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_movimentacoes_item_do_pedido_id_itens_do_pedido"),
        "movimentacoes",
        "itens_do_pedido",
        ["item_do_pedido_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_movimentacoes_item_do_pedido_id"), "movimentacoes", ["item_do_pedido_id"]
    )
    op.create_check_constraint(
        op.f("ck_movimentacoes_pedido_so_em_compra"),
        "movimentacoes",
        "item_do_pedido_id IS NULL OR (tipo = 'entrada' AND motivo IS NULL)",
    )


def downgrade() -> None:
    gravados = op.get_bind().scalar(
        sa.text("SELECT (SELECT count(*) FROM fornecedores) + (SELECT count(*) FROM pedidos)")
    )
    descartar = context.get_x_argument(as_dictionary=True).get("descartar_compras") == "sim"
    if gravados and not descartar:
        raise RuntimeError(
            f"Há {gravados} fornecedores ou pedidos de compra cadastrados, que a versão anterior "
            "não tem onde guardar (nem de quem foi cada compra). Baixe o relatório (a aba "
            "Movimentações leva o fornecedor de cada compra, e a Pedidos, o que falta chegar) "
            "e, para descartá-los, rode: "
            "alembic -x descartar_compras=sim downgrade 0009"
        )
    op.drop_constraint(op.f("ck_movimentacoes_pedido_so_em_compra"), "movimentacoes", type_="check")
    op.drop_index(op.f("ix_movimentacoes_item_do_pedido_id"), table_name="movimentacoes")
    op.drop_constraint(
        op.f("fk_movimentacoes_item_do_pedido_id_itens_do_pedido"),
        "movimentacoes",
        type_="foreignkey",
    )
    op.drop_column("movimentacoes", "item_do_pedido_id")
    op.drop_constraint(
        op.f("ck_movimentacoes_fornecedor_so_em_compra"), "movimentacoes", type_="check"
    )
    op.drop_index(op.f("ix_movimentacoes_fornecedor_id"), table_name="movimentacoes")
    op.drop_constraint(
        op.f("fk_movimentacoes_fornecedor_id_fornecedores"), "movimentacoes", type_="foreignkey"
    )
    op.drop_column("movimentacoes", "fornecedor_id")
    op.drop_index(op.f("ix_itens_do_pedido_insumo_id"), table_name="itens_do_pedido")
    op.drop_index(op.f("ix_itens_do_pedido_pedido_id"), table_name="itens_do_pedido")
    op.drop_table("itens_do_pedido")
    op.drop_index(op.f("ix_pedidos_usuario_id"), table_name="pedidos")
    op.drop_index(op.f("ix_pedidos_fornecedor_id"), table_name="pedidos")
    op.drop_table("pedidos")
    op.drop_table("fornecedores")
