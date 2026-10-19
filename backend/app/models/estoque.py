"""Insumos e as movimentações (entradas e saídas) de cada um.

O estoque atual NÃO é coluna: é a soma das movimentações, calculada na leitura.
Guardar o saldo seria ter duas fontes da verdade, que um dia discordam.
"""

from datetime import date

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

# Exata no banco, com 3 casas (grama no kg, mililitro no litro); float no Python,
# que é o que o motor de análise usa.
Quantidade = Numeric(12, 3, asdecimal=False)


class Insumo(Base):
    __tablename__ = "insumos"
    __table_args__ = (
        CheckConstraint("estoque_minimo >= 0", name="estoque_minimo_nao_negativo"),
        CheckConstraint("prazo_reposicao_dias >= 0", name="prazo_nao_negativo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    unidade: Mapped[str] = mapped_column(String(20))
    estoque_minimo: Mapped[float | None] = mapped_column(Quantidade)
    prazo_reposicao_dias: Mapped[int | None]
    # Gerado por `python -m app.demo`: a tela avisa, e `limpar` apaga só estes.
    demonstracao: Mapped[bool] = mapped_column(default=False, server_default=false())

    movimentacoes: Mapped[list[Movimentacao]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )


class Movimentacao(Base):
    __tablename__ = "movimentacoes"
    __table_args__ = (
        CheckConstraint("tipo IN ('entrada', 'saida')", name="tipo_valido"),
        CheckConstraint("quantidade > 0", name="quantidade_positiva"),
        # Validade é de lote, e lote só nasce numa entrada.
        CheckConstraint("validade IS NULL OR tipo = 'entrada'", name="validade_so_em_entrada"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    insumo_id: Mapped[int] = mapped_column(ForeignKey("insumos.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(7))
    data: Mapped[date]
    quantidade: Mapped[float] = mapped_column(Quantidade)
    validade: Mapped[date | None]
