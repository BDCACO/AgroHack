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
    # Do talhão, não do insumo: até a carência do defensivo aplicado acabar, não se colhe.
    "carencia",
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
    # Quanto vem numa embalagem (50 para o saco de 50 kg) e o mínimo que o fornecedor
    # aceita por pedido, na unidade do insumo. Sem eles, a sugestão de compra não arredonda.
    embalagem: float | None = None
    pedido_minimo: float | None = None


@dataclass(frozen=True)
class Lote:
    quantidade: float
    validade: date


@dataclass(frozen=True)
class Retirada:
    data: date
    quantidade: float


@dataclass(frozen=True)
class Descarte:
    """Saída que não é consumo: lote vencido jogado fora ou devolvido, produto estragado."""

    data: date
    quantidade: float


@dataclass(frozen=True)
class Entrada:
    data: date
    quantidade: float
    validade: date | None = None  # sem validade (calcário, por exemplo) não vira lote
    # R$ por unidade do insumo, o preço pago na compra. Opcional: sem ele, a análise
    # funciona igual, só não fala em reais.
    valor_unitario: float | None = None


@dataclass(frozen=True)
class Alerta:
    tipo: TipoAlerta
    gravidade: Gravidade
    justificativa: str
    # R$ envolvidos (o lote que vence, o capital parado), quando há custo médio. A conta
    # está no fim da justificativa; o número à parte serve para somar e ordenar.
    valor: float | None = None


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


def alertas_de_validade(
    lotes: Iterable[Lote], referencia: date, unidade: str, custo_medio: float | None = None
) -> list[Alerta]:
    alertas = []
    for lote in sorted(lotes, key=lambda lote: lote.validade):
        if lote.quantidade <= 0:
            continue
        dias = (lote.validade - referencia).days
        quantidade = quantidade_legivel(lote.quantidade, unidade)
        if dias < 0:
            tipo, gravidade = "vencido", "alta"
            texto = f"{quantidade} vencidos em {lote.validade:%d/%m/%Y}, há {dias_legivel(-dias)}."
        elif dias <= DIAS_AVISO_VENCIMENTO:
            quando = "hoje" if dias == 0 else f"em {dias_legivel(dias)}"
            tipo, gravidade = "vencimento_proximo", "media"
            texto = f"{quantidade} vencem em {lote.validade:%d/%m/%Y} ({quando})."
        else:
            continue
        valor = None
        if custo_medio is not None:
            valor = round(lote.quantidade * custo_medio, 2)
            preco = valor_pelo_custo_medio(custo_medio, unidade)
            texto += f" {preco}, são cerca de {dinheiro_legivel(valor)}."
        alertas.append(Alerta(tipo, gravidade, texto, valor))
    return alertas


def lotes_em_estoque(
    entradas: Iterable[Entrada],
    retiradas: Iterable[Retirada],
    descartes: Iterable[Descarte] = (),
) -> list[Lote]:
    """O que resta de cada lote com validade.

    A retirada não diz de qual lote saiu, então se supõe a boa prática: usa-se
    primeiro o que vence primeiro, entre os lotes que já tinham chegado na data da
    retirada. No mesmo dia, a entrada conta antes da retirada.

    Lote vencido na data da retirada fica por último: ninguém aplica produto vencido,
    e ele segue na prateleira (e no alerta) até ser descartado. Só sai dele o que os
    lotes bons não cobrem, para a soma dos lotes continuar igual ao estoque.

    O descarte é o contrário: sai primeiro do que venceu (ou vence) antes.
    """
    eventos = sorted(
        [(e.data, 0, e) for e in entradas]
        + [(r.data, 1, r) for r in retiradas]
        + [(d.data, 1, d) for d in descartes],
        key=lambda evento: evento[:2],
    )
    # [validade, saldo]; sem validade vai para o fim da fila (date.max) e não vira lote.
    disponiveis: list[list] = []
    for _, _, evento in eventos:
        if isinstance(evento, Entrada):
            disponiveis.append([evento.validade or date.max, evento.quantidade])
            continue
        falta = evento.quantidade
        dia = evento.data
        if isinstance(evento, Descarte):
            ordem = sorted(disponiveis, key=lambda lote: lote[0])
        else:
            ordem = sorted(disponiveis, key=lambda lote: (lote[0] < dia, lote[0]))
        for lote in ordem:
            usado = min(lote[1], falta)
            lote[1] -= usado
            falta -= usado
            if falta <= 0:
                break
    return [
        Lote(round(saldo, 3), validade)
        for validade, saldo in disponiveis
        if validade != date.max and round(saldo, 3) > 0
    ]


def custo_medio(entradas: Iterable[Entrada]) -> float | None:
    """Preço médio pago, ponderado pela quantidade de cada compra: 1000 kg a R$ 3,00 e
    500 kg a R$ 3,60 dão R$ 3,20, e não a média simples de R$ 3,30.

    Só as entradas com preço entram na conta; sem nenhuma, não há custo (None), em vez
    de um zero que pareceria produto de graça.

    Em centavos: é o preço que a tela mostra, e toda conta em reais parte dele. Com as
    casas a mais, "R$ 3,16/kg" vezes 700 kg daria R$ 2.210,96 em vez dos R$ 2.212,00 que
    o produtor confere à mão.
    """
    com_preco = [e for e in entradas if e.valor_unitario is not None]
    quantidade = sum(e.quantidade for e in com_preco)
    if not quantidade:
        return None
    return round(sum(e.quantidade * e.valor_unitario for e in com_preco) / quantidade, 2)


_PADRAO_BR = str.maketrans(",.", ".,")


def quantidade_legivel(valor: float, unidade: str) -> str:
    """1234.5, "kg" → "1.234,5 kg". Duas casas porque defensivo se usa em frações de litro."""
    numero = f"{valor:,.2f}".translate(_PADRAO_BR).rstrip("0").rstrip(",")
    return f"{numero} {unidade}"


def valor_pelo_custo_medio(custo_medio: float, unidade: str) -> str:
    """O começo da frase que põe preço numa quantidade: a conta fica à vista."""
    return f"Pelo custo médio de {dinheiro_legivel(custo_medio)}/{unidade}"


def dinheiro_legivel(valor: float) -> str:
    """1234.5 → "R$ 1.234,50". Sempre com os centavos, como o produtor lê numa nota."""
    return f"R$ {valor:,.2f}".translate(_PADRAO_BR)


def dias_legivel(dias: float) -> str:
    inteiro = round(dias)
    return "1 dia" if inteiro == 1 else f"{inteiro} dias"
