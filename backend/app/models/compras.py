"""Fornecedores e pedidos de compra: o ciclo que fecha a reposição sugerida.

A análise sugere "pedir 14 sacos de ureia"; o pedido registra que foi pedido (a quem,
quanto, para quando), e o recebimento vira a entrada no estoque. O que foi pedido e não
chegou entra na análise: sem isso, ela manda comprar de novo o que está a caminho.
"""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, false, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.estoque import Quantidade, ValorUnitario
from app.models.usuario import Usuario

if TYPE_CHECKING:
    from app.models.estoque import Insumo

SITUACOES = ("aberto", "parcial", "recebido", "cancelado")


class Fornecedor(Base):
    """A revenda, a cooperativa ou a agropecuária de quem se compra. Não se apaga quem tem
    compra ou pedido registrado: desativa (a história de preços continua valendo)."""

    __tablename__ = "fornecedores"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    contato: Mapped[str | None] = mapped_column(String(120))  # com quem falar: "Seu Antônio"
    telefone: Mapped[str | None] = mapped_column(String(30))  # o WhatsApp da revenda
    cidade: Mapped[str | None] = mapped_column(String(80))
    observacao: Mapped[str | None] = mapped_column(String(500))
    # Desativado sai das escolhas (novo pedido, sugestão), mas as compras dele ficam.
    ativo: Mapped[bool] = mapped_column(default=True, server_default=true())
    # Como no insumo: gerado por `python -m app.demo`, e `limpar` apaga só estes.
    demonstracao: Mapped[bool] = mapped_column(default=False, server_default=false())


class Pedido(Base):
    """O que se pediu a um fornecedor, num dia, e o que já chegou. `situacao` muda com o
    recebimento (parcial, recebido) ou com o cancelamento."""

    __tablename__ = "pedidos"
    __table_args__ = (
        CheckConstraint(
            "situacao IN ('aberto', 'parcial', 'recebido', 'cancelado')", name="situacao_valida"
        ),
        CheckConstraint("previsto_para >= feito_em", name="previsto_depois_de_feito"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Opcional: o pedido feito por telefone a quem ainda não está cadastrado vale igual.
    # RESTRICT: o fornecedor com pedido não se apaga, desativa.
    fornecedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("fornecedores.id", ondelete="RESTRICT"), index=True
    )
    situacao: Mapped[str] = mapped_column(String(9), default="aberto")
    feito_em: Mapped[date]
    # Sem ela, a análise desconta o pedido mas não sabe se ele chega antes de o estoque
    # acabar, e diz isso.
    previsto_para: Mapped[date | None]
    observacao: Mapped[str | None] = mapped_column(String(500))
    # Quem fez o pedido (auditoria), como em movimentacoes.usuario_id.
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), index=True
    )

    fornecedor: Mapped[Fornecedor | None] = relationship(lazy="joined")
    usuario: Mapped[Usuario | None] = relationship(lazy="joined")
    itens: Mapped[list[ItemDoPedido]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ItemDoPedido.id",
        lazy="selectin",
    )


class ItemDoPedido(Base):
    __tablename__ = "itens_do_pedido"
    __table_args__ = (
        # Uma linha por insumo no pedido: o recebimento aponta para ela sem ambiguidade.
        UniqueConstraint("pedido_id", "insumo_id"),
        CheckConstraint("quantidade > 0", name="quantidade_positiva"),
        CheckConstraint("valor_unitario > 0", name="valor_unitario_positivo"),
        CheckConstraint("quantidade_recebida >= 0", name="recebida_nao_negativa"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos.id", ondelete="CASCADE"), index=True)
    # CASCADE, como as movimentações: remover o insumo cadastrado por engano leva o que foi
    # pedido dele (e o pedido que fica vazio sai junto, no serviço).
    insumo_id: Mapped[int] = mapped_column(ForeignKey("insumos.id", ondelete="CASCADE"), index=True)
    quantidade: Mapped[float] = mapped_column(Quantidade)
    # R$ por unidade combinado com a revenda. Opcional: a entrada recebida o herda, se a
    # nota não trouxer outro.
    valor_unitario: Mapped[float | None] = mapped_column(ValorUnitario)
    # A soma das entradas recebidas por este item. Pode passar da quantidade: a carga que
    # veio a mais entrou no galpão, e o estoque tem de dizer isso.
    quantidade_recebida: Mapped[float] = mapped_column(Quantidade, default=0, server_default="0")

    insumo: Mapped[Insumo] = relationship(lazy="joined")

    @property
    def falta_receber(self) -> float:
        return round(max(self.quantidade - self.quantidade_recebida, 0), 3)
