"""Insumos e as movimentações (entradas e saídas) de cada um.

O estoque atual NÃO é coluna: é a soma das movimentações, calculada na leitura.
Guardar o saldo seria ter duas fontes da verdade, que um dia discordam.
"""

from datetime import date
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Uuid, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

# Exata no banco, com 3 casas (grama no kg, mililitro no litro); float no Python,
# que é o que o motor de análise usa.
Quantidade = Numeric(12, 3, asdecimal=False)
# Hectares, com duas casas, como na escritura e no CAR.
Area = Numeric(10, 2, asdecimal=False)
# R$ por unidade do insumo. Quatro casas: o preço por grama ou por mililitro de um
# defensivo caro tem centavos depois da vírgula.
ValorUnitario = Numeric(14, 4, asdecimal=False)


class Insumo(Base):
    __tablename__ = "insumos"
    __table_args__ = (
        CheckConstraint("estoque_minimo >= 0", name="estoque_minimo_nao_negativo"),
        CheckConstraint("prazo_reposicao_dias >= 0", name="prazo_nao_negativo"),
        CheckConstraint("embalagem > 0", name="embalagem_positiva"),
        CheckConstraint("pedido_minimo >= 0", name="pedido_minimo_nao_negativo"),
        CheckConstraint("carencia_dias >= 0", name="carencia_nao_negativa"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    unidade: Mapped[str] = mapped_column(String(20))
    estoque_minimo: Mapped[float | None] = mapped_column(Quantidade)
    prazo_reposicao_dias: Mapped[int | None]
    # Na unidade do insumo: 50 para o saco de 50 kg. A reposição sugere embalagens
    # fechadas, e nunca menos que o pedido mínimo do fornecedor.
    embalagem: Mapped[float | None] = mapped_column(Quantidade)
    pedido_minimo: Mapped[float | None] = mapped_column(Quantidade)
    # Dias mínimos entre aplicar e colher ou abater (a bula do defensivo). 0 = não tem;
    # vazio = não informada, e a carência do talhão diz que não a considerou.
    carencia_dias: Mapped[int | None]
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
        # Movimentação com motivo não é consumo: não entra no ritmo nem nos alertas de
        # consumo. Descarte é sempre saída; o ajuste de inventário vai para os dois lados.
        CheckConstraint(
            "motivo IS NULL OR (motivo = 'descarte' AND tipo = 'saida') OR motivo = 'inventario'",
            name="motivo_valido",
        ),
        CheckConstraint("valor_unitario > 0", name="valor_unitario_positivo"),
        # Preço é o que se pagou numa compra: nem saída nem ajuste de inventário têm.
        CheckConstraint(
            "valor_unitario IS NULL OR (tipo = 'entrada' AND motivo IS NULL)",
            name="valor_so_em_compra",
        ),
        # Talhão é para onde o insumo foi aplicado: só a retirada para uso tem. Compra,
        # descarte e ajuste de inventário não saem para a lavoura.
        CheckConstraint(
            "talhao_id IS NULL OR (tipo = 'saida' AND motivo IS NULL)",
            name="talhao_so_em_aplicacao",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    insumo_id: Mapped[int] = mapped_column(ForeignKey("insumos.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(7))
    data: Mapped[date]
    quantidade: Mapped[float] = mapped_column(Quantidade)
    validade: Mapped[date | None]
    # Coluna à parte, e não um terceiro `tipo`: para o saldo, o site e o app, o
    # descarte continua sendo uma saída.
    motivo: Mapped[str | None] = mapped_column(String(10))
    # Opcional: sem preço, tudo funciona igual; com ele, a análise fala em reais.
    valor_unitario: Mapped[float | None] = mapped_column(ValorUnitario)
    # Gerado pelo app no celular, antes de enviar: o reenvio de um lançamento feito sem
    # sinal é reconhecido por ele e não vira duplicata. Vazio no que veio do site, da
    # importação e da contagem do galpão.
    uuid: Mapped[UUID | None] = mapped_column(Uuid, unique=True)
    # Opcional: a retirada sem talhão continua valendo para o estoque e o consumo. RESTRICT:
    # remover o talhão não pode apagar nem esvaziar o registro de onde cada insumo foi.
    talhao_id: Mapped[int | None] = mapped_column(
        ForeignKey("talhoes.id", ondelete="RESTRICT"), index=True
    )


class Talhao(Base):
    """Onde o insumo foi aplicado: a área de lavoura ou o pasto. A retirada lançada num
    talhão diz para onde o produto foi, e com isso o custo por hectare e a carência."""

    __tablename__ = "talhoes"
    __table_args__ = (CheckConstraint("area_ha > 0", name="area_positiva"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    # O divisor do custo por hectare: por isso obrigatória e maior que zero.
    area_ha: Mapped[float] = mapped_column(Area)
    cultura: Mapped[str | None] = mapped_column(String(60))  # "Soja", "Pasto"...
    # Como no insumo: gerado por `python -m app.demo`, e `limpar` apaga só estes.
    demonstracao: Mapped[bool] = mapped_column(default=False, server_default=false())
