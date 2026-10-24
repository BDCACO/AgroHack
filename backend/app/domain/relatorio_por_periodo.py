"""O relatório por período: em cada mês (semana ou dia), quanto se usou de cada insumo,
quanto se gastou em compras e quanto se perdeu, com os totais por categoria e por
fornecedor.

Puro, como o resto do domínio: recebe os lançamentos e os insumos já lidos do banco e
devolve as somas. As regras que importam ao produtor estão aqui, testáveis sem banco:

- **Consumo** é só a retirada para uso. Descarte e falta da contagem são perda; a sobra da
  contagem não é compra nem consumo. Como no ritmo de consumo da análise.
- **Quantidade só se soma dentro do mesmo insumo.** 150 kg de ureia e 4 L de glifosato
  não dão "154" de nada; em reais (pelo custo médio), sim, se somam.
- **Gasto** é o que se pagou nas compras com preço; a compra sem preço fica fora, e o
  relatório diz quantas.
- **Perda** é o descarte e a falta da contagem pelo custo médio de hoje, a mesma conta do
  GET /resumo.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

Agrupamento = Literal["mes", "semana", "dia"]

# Pontos num gráfico que ainda se lê na tela do celular: um ano e um mês por dia, quase
# oito anos por semana, mais de trinta por mês. Acima, a resposta pesaria sem dizer mais.
MAXIMO_DE_PERIODOS = 400

_MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
# Sempre no plural: o teto só se passa com mais de um.
_PERIODOS = {"mes": "meses", "semana": "semanas", "dia": "dias"}


class MuitosPeriodos(Exception):
    def __init__(self, quantos: int, agrupar: Agrupamento) -> None:
        super().__init__(
            f"São {quantos} {_PERIODOS[agrupar]} no período, e o relatório mostra até "
            f"{MAXIMO_DE_PERIODOS}: encurte o período ou agrupe por um intervalo maior."
        )


@dataclass(frozen=True)
class InsumoDoRelatorio:
    id: int
    nome: str
    unidade: str
    categoria_id: int | None
    categoria: str | None
    # O de hoje, pelas compras com preço (o mesmo da tela do insumo). None sem preço.
    custo_medio: float | None = None


@dataclass(frozen=True)
class Lancamento:
    """Uma movimentação, com o que as somas usam."""

    data: date
    insumo_id: int
    tipo: Literal["entrada", "saida"]
    motivo: str | None  # None, "descarte" ou "inventario"
    quantidade: float
    valor_unitario: float | None = None
    fornecedor_id: int | None = None
    fornecedor: str | None = None  # o nome


@dataclass(frozen=True)
class ConsumoDoInsumo:
    insumo_id: int
    insumo: str
    unidade: str
    quantidade: float  # na unidade do insumo
    valor: float | None  # quantidade × custo médio; None sem preço


@dataclass(frozen=True)
class TotalDaCategoria:
    categoria_id: int | None  # None: os insumos sem categoria
    categoria: str | None
    gasto: float  # nas compras com preço
    consumo: float  # o que se usou, em R$, dos insumos com custo médio
    perdas: float


@dataclass(frozen=True)
class TotalDoFornecedor:
    fornecedor_id: int | None  # None: as compras sem fornecedor
    fornecedor: str | None
    gasto: float
    compras: int
    compras_sem_preco: int


@dataclass(frozen=True)
class Totais:
    consumo: list[ConsumoDoInsumo]  # pelo nome do insumo
    gasto: float
    compras_sem_preco: int  # fora do gasto
    perdas: float
    perdas_sem_preco: int  # perdas de insumo sem custo médio, fora do valor das perdas
    por_categoria: list[TotalDaCategoria]  # pelo nome; sem categoria por último
    por_fornecedor: list[TotalDoFornecedor]  # pelo nome; sem fornecedor por último


@dataclass(frozen=True)
class _Intervalo:
    inicio: date
    fim: date  # inclusive
    rotulo: str  # "out/2026", "semana de 19/10/2026", "24/10/2026"


@dataclass(frozen=True)
class Periodo(Totais, _Intervalo):
    """Um mês, semana ou dia: o intervalo e as somas dele. Sem movimento, tudo zero."""


@dataclass(frozen=True)
class RelatorioPorPeriodo:
    desde: date
    ate: date
    agrupar: Agrupamento
    periodos: list[Periodo]  # do mais antigo ao mais recente, sem buraco
    total: Totais  # do período inteiro
    limitacoes: list[str]


def periodos(desde: date, ate: date, agrupar: Agrupamento) -> list[tuple[date, date, str]]:
    """Os intervalos de `desde` a `ate`, cortados nas pontas: pedir de 15/08 a 10/10 por
    mês dá 15/08 a 31/08, setembro inteiro e 01/10 a 10/10. A semana vai de segunda a
    domingo. Acima de MAXIMO_DE_PERIODOS, MuitosPeriodos (contado antes de montar a
    lista: um período de séculos por dia não chega a ser montado)."""
    if (quantos := _quantos(desde, ate, agrupar)) > MAXIMO_DE_PERIODOS:
        raise MuitosPeriodos(quantos, agrupar)
    intervalos = []
    comeco = _comeco(desde, agrupar)
    while comeco <= ate:
        seguinte = _seguinte(comeco, agrupar)
        fim = min(seguinte - timedelta(days=1), ate)
        intervalos.append((max(comeco, desde), fim, _rotulo(comeco, agrupar)))
        comeco = seguinte
    return intervalos


def relatorio(
    lancamentos: Iterable[Lancamento],
    insumos: Mapping[int, InsumoDoRelatorio],
    desde: date,
    ate: date,
    agrupar: Agrupamento,
) -> RelatorioPorPeriodo:
    intervalos = periodos(desde, ate, agrupar)
    no_periodo = sorted(
        (lanc for lanc in lancamentos if desde <= lanc.data <= ate), key=lambda lanc: lanc.data
    )
    por_periodo = []
    for inicio, fim, rotulo in intervalos:
        deste = [lanc for lanc in no_periodo if inicio <= lanc.data <= fim]
        somas = _somar(deste, insumos)
        por_periodo.append(Periodo(inicio=inicio, fim=fim, rotulo=rotulo, **vars(somas)))
    total = _somar(no_periodo, insumos)
    return RelatorioPorPeriodo(
        desde, ate, agrupar, por_periodo, total, _limitacoes(total, no_periodo, insumos)
    )


def _somar(lancamentos: list[Lancamento], insumos: Mapping[int, InsumoDoRelatorio]) -> Totais:
    consumo: dict[int, float] = {}
    gasto = perdas = 0.0
    compras_sem_preco = perdas_sem_preco = 0
    categorias: dict[int | None, dict[str, float]] = {}
    fornecedores: dict[int | None, dict] = {}

    def da_categoria(insumo: InsumoDoRelatorio) -> dict[str, float]:
        return categorias.setdefault(
            insumo.categoria_id, {"gasto": 0.0, "consumo": 0.0, "perdas": 0.0}
        )

    for lanc in lancamentos:
        insumo = insumos[lanc.insumo_id]
        if lanc.tipo == "saida" and lanc.motivo is None:
            # Por insumo: a soma nunca atravessa unidades.
            consumo[insumo.id] = consumo.get(insumo.id, 0.0) + lanc.quantidade
            if insumo.custo_medio is not None:
                da_categoria(insumo)["consumo"] += lanc.quantidade * insumo.custo_medio
            else:
                da_categoria(insumo)
        elif lanc.tipo == "saida":  # descarte ou falta da contagem
            categoria = da_categoria(insumo)
            if insumo.custo_medio is None:
                perdas_sem_preco += 1
            else:
                valor = lanc.quantidade * insumo.custo_medio
                perdas += valor
                categoria["perdas"] += valor
        elif lanc.motivo is None:  # compra (a sobra da contagem não é)
            categoria = da_categoria(insumo)
            fornecedor = fornecedores.setdefault(
                lanc.fornecedor_id,
                {"nome": lanc.fornecedor, "gasto": 0.0, "compras": 0, "sem_preco": 0},
            )
            fornecedor["compras"] += 1
            if lanc.valor_unitario is None:
                compras_sem_preco += 1
                fornecedor["sem_preco"] += 1
            else:
                valor = lanc.quantidade * lanc.valor_unitario
                gasto += valor
                categoria["gasto"] += valor
                fornecedor["gasto"] += valor

    nomes_das_categorias = {i.categoria_id: i.categoria for i in insumos.values()}
    return Totais(
        consumo=sorted(
            (_consumo(insumos[insumo_id], quantidade) for insumo_id, quantidade in consumo.items()),
            key=lambda c: c.insumo,
        ),
        gasto=round(gasto, 2),
        compras_sem_preco=compras_sem_preco,
        perdas=round(perdas, 2),
        perdas_sem_preco=perdas_sem_preco,
        por_categoria=sorted(
            (
                TotalDaCategoria(
                    categoria_id,
                    nomes_das_categorias[categoria_id],
                    round(somas["gasto"], 2),
                    round(somas["consumo"], 2),
                    round(somas["perdas"], 2),
                )
                for categoria_id, somas in categorias.items()
            ),
            key=lambda c: (c.categoria is None, c.categoria or ""),
        ),
        por_fornecedor=sorted(
            (
                TotalDoFornecedor(
                    fornecedor_id,
                    somas["nome"],
                    round(somas["gasto"], 2),
                    somas["compras"],
                    somas["sem_preco"],
                )
                for fornecedor_id, somas in fornecedores.items()
            ),
            key=lambda f: (f.fornecedor is None, f.fornecedor or ""),
        ),
    )


def _consumo(insumo: InsumoDoRelatorio, quantidade: float) -> ConsumoDoInsumo:
    valor = None if insumo.custo_medio is None else round(quantidade * insumo.custo_medio, 2)
    # Quantidades têm 3 casas no banco: arredondar tira o resíduo do float (0,1 + 0,2).
    return ConsumoDoInsumo(insumo.id, insumo.nome, insumo.unidade, round(quantidade, 3), valor)


def _limitacoes(
    total: Totais, lancamentos: list[Lancamento], insumos: Mapping[int, InsumoDoRelatorio]
) -> list[str]:
    limitacoes = []
    if total.compras_sem_preco:
        n = total.compras_sem_preco
        limitacoes.append(
            "1 compra sem preço ficou fora do gasto."
            if n == 1
            else f"{n} compras sem preço ficaram fora do gasto."
        )
    if total.perdas_sem_preco:
        n = total.perdas_sem_preco
        limitacoes.append(
            "1 perda de insumo sem preço ficou fora do valor das perdas."
            if n == 1
            else f"{n} perdas de insumos sem preço ficaram fora do valor das perdas."
        )
    sem_valor = sorted(c.insumo for c in total.consumo if c.valor is None)
    if sem_valor:
        limitacoes.append(
            f"Consumo sem valor em reais (insumo sem compra com preço): {', '.join(sem_valor)}."
        )
    if total.perdas or any(c.valor for c in total.consumo):
        limitacoes.append(
            "Consumo e perdas em reais pelo custo médio de hoje, não pelo preço da época."
        )
    return limitacoes


def _quantos(desde: date, ate: date, agrupar: Agrupamento) -> int:
    if agrupar == "dia":
        return (ate - desde).days + 1
    if agrupar == "semana":
        return (_comeco(ate, "semana") - _comeco(desde, "semana")).days // 7 + 1
    return (ate.year - desde.year) * 12 + ate.month - desde.month + 1


def _comeco(dia: date, agrupar: Agrupamento) -> date:
    if agrupar == "mes":
        return dia.replace(day=1)
    if agrupar == "semana":
        return dia - timedelta(days=dia.weekday())  # a segunda-feira
    return dia


def _seguinte(comeco: date, agrupar: Agrupamento) -> date:
    if agrupar == "mes":
        return date(comeco.year + comeco.month // 12, comeco.month % 12 + 1, 1)
    return comeco + timedelta(days=7 if agrupar == "semana" else 1)


def _rotulo(comeco: date, agrupar: Agrupamento) -> str:
    if agrupar == "mes":
        return f"{_MESES[comeco.month - 1]}/{comeco.year}"
    if agrupar == "semana":
        return f"semana de {comeco:%d/%m/%Y}"
    return f"{comeco:%d/%m/%Y}"
