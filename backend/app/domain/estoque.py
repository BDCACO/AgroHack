"""Regras de estoque de insumos que não dependem de histórico de consumo.

Puras: sem I/O, sem banco, sem relógio. A data de referência entra como parâmetro,
para que a mesma entrada dê sempre o mesmo resultado — e o teste não dependa do dia.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Literal

Gravidade = Literal["alta", "media", "baixa"]
TipoAlerta = Literal[
    "abaixo_do_minimo",
    "risco_de_falta",
    "vencido",
    "vencimento_proximo",
    "excesso",
    "baixa_movimentacao",
    "consumo_incomum",
]

# Lote a 30 dias da validade ainda dá tempo de planejar o uso ou negociar troca.
DIAS_AVISO_VENCIMENTO = 30


@dataclass(frozen=True)
class Insumo:
    nome: str
    unidade: str  # "kg", "L", "sc"... só aparece na justificativa
    estoque_atual: float
    estoque_minimo: float | None = None
    # Dias entre fazer o pedido e o insumo chegar. Sem ele, a análise assume um
    # padrão e diz isso nas limitações.
    prazo_reposicao_dias: int | None = None


@dataclass(frozen=True)
class Lote:
    quantidade: float
    validade: date


@dataclass(frozen=True)
class Retirada:
    data: date
    quantidade: float


@dataclass(frozen=True)
class Alerta:
    tipo: TipoAlerta
    gravidade: Gravidade
    justificativa: str


def alerta_estoque_minimo(insumo: Insumo) -> Alerta | None:
    if insumo.estoque_minimo is None or insumo.estoque_atual >= insumo.estoque_minimo:
        return None
    minimo = quantidade_legivel(insumo.estoque_minimo, insumo.unidade)
    if insumo.estoque_atual <= 0:
        return Alerta("abaixo_do_minimo", "alta", f"Estoque zerado; o mínimo definido é {minimo}.")
    atual = quantidade_legivel(insumo.estoque_atual, insumo.unidade)
    return Alerta(
        "abaixo_do_minimo", "media", f"Estoque atual de {atual}, abaixo do mínimo de {minimo}."
    )


def alertas_de_validade(lotes: Iterable[Lote], referencia: date, unidade: str) -> list[Alerta]:
    alertas = []
    for lote in sorted(lotes, key=lambda lote: lote.validade):
        if lote.quantidade <= 0:
            continue
        dias = (lote.validade - referencia).days
        quantidade = quantidade_legivel(lote.quantidade, unidade)
        if dias < 0:
            alertas.append(
                Alerta(
                    "vencido",
                    "alta",
                    f"{quantidade} vencidos em {lote.validade:%d/%m/%Y}, há {dias_legivel(-dias)}.",
                )
            )
        elif dias <= DIAS_AVISO_VENCIMENTO:
            quando = "hoje" if dias == 0 else f"em {dias_legivel(dias)}"
            alertas.append(
                Alerta(
                    "vencimento_proximo",
                    "media",
                    f"{quantidade} vencem em {lote.validade:%d/%m/%Y} ({quando}).",
                )
            )
    return alertas


_PADRAO_BR = str.maketrans(",.", ".,")


def quantidade_legivel(valor: float, unidade: str) -> str:
    """1234.5, "kg" → "1.234,5 kg". Duas casas porque defensivo se usa em frações de litro."""
    numero = f"{valor:,.2f}".translate(_PADRAO_BR).rstrip("0").rstrip(",")
    return f"{numero} {unidade}"


def dias_legivel(dias: float) -> str:
    inteiro = round(dias)
    return "1 dia" if inteiro == 1 else f"{inteiro} dias"
