"""Regras do talhão: até quando não se pode colher (a carência dos defensivos aplicados) e
quanto custou o que foi aplicado nele.

Puras, como as do estoque: sem I/O, sem banco, sem relógio. A data de referência entra
como parâmetro.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from app.domain.estoque import Alerta, dias_legivel


@dataclass(frozen=True)
class Aplicacao:
    """Uma retirada para uso lançada num talhão: o insumo foi aplicado ali."""

    data: date
    insumo_id: int
    insumo: str
    unidade: str
    quantidade: float
    # Dias mínimos entre aplicar e colher ou abater, da bula. 0 = o insumo não tem carência
    # (a ureia); None = não cadastrada, e então o prazo dele não é conhecido.
    carencia_dias: int | None = None


@dataclass(frozen=True)
class Carencia:
    # Quando a última carência acaba: max(data + carência) entre as aplicações com carência
    # cadastrada. None se nenhuma tem.
    colheita_liberada_em: date | None
    alertas: list[Alerta]
    limitacoes: list[str]


def carencia(talhao: str, aplicacoes: Iterable[Aplicacao], referencia: date) -> Carencia:
    """A colheita fica liberada quando a ÚLTIMA carência acaba, e não a da aplicação mais
    recente: um inseticida de 30 dias aplicado há 10 prende o talhão mais que um fungicida
    de 3 dias aplicado ontem.

    Enquanto não libera, o alerta é sempre de gravidade alta. Colher antes é proibido, e o
    erro não tem conserto: resíduo no alimento, carga recusada, multa. Não há meio-termo
    entre proibido e permitido, e não se sabe quando o produtor pretende colher, então a
    distância até a liberação não diminui o risco.
    """
    # A aplicação depois da referência ainda não aconteceu, para esta conta.
    feitas = [a for a in aplicacoes if a.data <= referencia]
    com_prazo = [a for a in feitas if a.carencia_dias is not None]
    limitacoes = []
    if sem_prazo := sorted({a.insumo for a in feitas if a.carencia_dias is None}):
        quantos = len(sem_prazo)
        sujeito = "1 insumo aplicado" if quantos == 1 else f"{quantos} insumos aplicados"
        dele = "dele" if quantos == 1 else "deles"
        limitacoes.append(
            f"{sujeito} sem carência cadastrada ({', '.join(sem_prazo)}): o prazo {dele} não é "
            "considerado. Cadastre a carência na tela de Insumos (0 se não tem)."
        )
    if not com_prazo:
        return Carencia(None, [], limitacoes)

    # Empate na data de liberação: vale a aplicação mais recente, a que o produtor lembra.
    decisiva = max(com_prazo, key=lambda a: (_liberada(a), a.data, a.insumo))
    liberada = _liberada(decisiva)
    alertas = []
    if liberada > referencia:
        faltam = (liberada - referencia).days
        falta = "falta" if faltam == 1 else "faltam"
        alertas.append(
            Alerta(
                "carencia",
                "alta",
                f"{talhao}: não colher nem abater antes de {liberada:%d/%m/%Y} ({falta} "
                f"{dias_legivel(faltam)}). {decisiva.insumo} aplicado em "
                f"{decisiva.data:%d/%m/%Y}, carência de {dias_legivel(decisiva.carencia_dias)}.",
            )
        )
    if any(a.carencia_dias for a in com_prazo):
        limitacoes.append(
            "A carência é a do cadastro de cada insumo: confira na bula ou no receituário, "
            "porque ela pode mudar com a cultura."
        )
    return Carencia(liberada, alertas, limitacoes)


@dataclass(frozen=True)
class ConsumoNoTalhao:
    insumo_id: int
    insumo: str
    unidade: str
    quantidade: float
    custo: float | None  # None: o insumo não tem compra com preço


@dataclass(frozen=True)
class CustoDoTalhao:
    # R$ do que foi aplicado. None se houve aplicação e nenhuma tem preço: um zero pareceria
    # insumo de graça. Zero de verdade só quando nada foi aplicado.
    total: float | None
    por_hectare: float | None
    consumo: list[ConsumoNoTalhao]  # o que mais pesou no custo primeiro
    limitacoes: list[str]


def custo(
    aplicacoes: Iterable[Aplicacao],
    custos_medios: Mapping[int, float | None],
    area_ha: float,
    desde: date | None = None,
    ate: date | None = None,
) -> CustoDoTalhao:
    """Quantidade aplicada × custo médio do insumo, somado no talhão e dividido pela área.

    O período (`desde` e `ate`, os dois inclusive) recorta uma safra. O custo médio é o de
    hoje, das compras com preço: as retiradas não dizem de qual compra saíram, e é o mesmo
    custo que o resto do CampoCerto usa para o estoque e as perdas.
    """
    no_periodo = [
        a
        for a in aplicacoes
        if (desde is None or a.data >= desde) and (ate is None or a.data <= ate)
    ]
    por_insumo: dict[int, list[Aplicacao]] = {}
    for aplicacao in no_periodo:
        por_insumo.setdefault(aplicacao.insumo_id, []).append(aplicacao)
    consumo = []
    for insumo_id, do_insumo in por_insumo.items():
        # Quantidades têm no máximo 3 casas: o arredondamento tira o resíduo do float.
        quantidade = round(sum(a.quantidade for a in do_insumo), 3)
        custo_medio = custos_medios.get(insumo_id)
        valor = None if custo_medio is None else round(quantidade * custo_medio, 2)
        consumo.append(
            ConsumoNoTalhao(insumo_id, do_insumo[0].insumo, do_insumo[0].unidade, quantidade, valor)
        )
    consumo.sort(key=lambda c: (c.custo is None, -(c.custo or 0), c.insumo))

    com_preco = [c.custo for c in consumo if c.custo is not None]
    total = round(sum(com_preco), 2) if com_preco or not consumo else None
    limitacoes = []
    if com_preco:
        limitacoes.append(
            "Custo pelo custo médio de hoje de cada insumo, não pelo preço pago na época da "
            "aplicação."
        )
    sem_preco = [a for a in no_periodo if custos_medios.get(a.insumo_id) is None]
    if sem_preco:
        nomes = sorted({a.insumo for a in sem_preco})
        quantas = len(sem_preco)
        sujeito = "1 aplicação" if quantas == 1 else f"{quantas} aplicações"
        verbo = "fica" if quantas == 1 else "ficam"
        desses = "desse insumo" if len(nomes) == 1 else "desses insumos"
        limitacoes.append(
            f"{sujeito} sem preço ({', '.join(nomes)}) {verbo} fora do custo: lance o preço das "
            f"compras {desses}."
        )
    return CustoDoTalhao(
        total=total,
        por_hectare=None if total is None else round(total / area_ha, 2),
        consumo=consumo,
        limitacoes=limitacoes,
    )


def _liberada(aplicacao: Aplicacao) -> date:
    # No dia data + carência o intervalo mínimo já se cumpriu: dali em diante pode colher.
    return aplicacao.data + timedelta(days=aplicacao.carencia_dias)
