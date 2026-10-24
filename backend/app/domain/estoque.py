"""Regras de saldo de estoque. Puro: sem banco, sem framework, sem relógio.

O saldo de um insumo NÃO é gravado: é a soma das compras menos a soma das
retiradas. Um saldo gravado ao lado das movimentações pode divergir delas, e
aí o sistema passa a ter duas respostas para a mesma pergunta.
"""

from decimal import Decimal
from enum import StrEnum

from app.domain.erros import EstoqueInsuficiente


class TipoMovimentacao(StrEnum):
    COMPRA = "compra"
    RETIRADA = "retirada"


def efeito_no_saldo(tipo: TipoMovimentacao, quantidade: Decimal) -> Decimal:
    """Quanto a movimentação soma (compra) ou subtrai (retirada) do saldo."""
    return quantidade if tipo is TipoMovimentacao.COMPRA else -quantidade


def validar_inclusao(
    saldo_atual: Decimal, tipo: TipoMovimentacao, quantidade: Decimal, unidade: str
) -> None:
    """Retirada maior que o saldo deixaria o estoque negativo — recusada."""
    if tipo is TipoMovimentacao.RETIRADA and quantidade > saldo_atual:
        raise EstoqueInsuficiente(
            f"Retirada de {_fmt(quantidade)} {unidade} maior que o saldo "
            f"disponível ({_fmt(saldo_atual)} {unidade})."
        )


def validar_remocao(
    saldo_atual: Decimal, tipo: TipoMovimentacao, quantidade: Decimal, unidade: str
) -> None:
    """Remover uma compra cujo estoque já foi retirado deixaria o saldo negativo."""
    if saldo_atual - efeito_no_saldo(tipo, quantidade) < 0:
        raise EstoqueInsuficiente(
            f"Remover esta compra deixaria o saldo negativo: {_fmt(quantidade)} {unidade} "
            f"comprados, mas só {_fmt(saldo_atual)} {unidade} em estoque. "
            "Remova antes as retiradas correspondentes."
        )


def _fmt(valor: Decimal) -> str:
    """Quantidade no formato brasileiro, sem zeros à direita: 1.250,5."""
    texto = f"{valor.normalize():,f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")
