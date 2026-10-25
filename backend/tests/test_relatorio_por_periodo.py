"""O relatório por período (mês, semana ou dia): consumo, gasto, perdas e os totais por
categoria e por fornecedor. A agregação pura, sem banco; a rota está em
test_relatorio_por_periodo_rota.py."""

import random
from dataclasses import fields
from datetime import date

import pytest

from app.domain.relatorio_por_periodo import (
    DATA_MAXIMA,
    DATA_MINIMA,
    MAXIMO_DE_PERIODOS,
    DataForaDaFaixa,
    InsumoDoRelatorio,
    Lancamento,
    MuitosPeriodos,
    Totais,
    periodos,
    relatorio,
)

UREIA = InsumoDoRelatorio(1, "Ureia", "kg", 10, "Fertilizante", custo_medio=3.0)
GLIFOSATO = InsumoDoRelatorio(2, "Glifosato", "L", 20, "Defensivo agrícola", custo_medio=25.0)
# Sem compra com preço: o consumo e a perda dele não viram reais.
SAL = InsumoDoRelatorio(3, "Sal mineral", "kg", None, None, custo_medio=None)
INSUMOS = {i.id: i for i in (UREIA, GLIFOSATO, SAL)}


def compra(
    dia: date, insumo: InsumoDoRelatorio, quantidade: float, preco: float | None = None, **outros
) -> Lancamento:
    return Lancamento(dia, insumo.id, "entrada", None, quantidade, preco, **outros)


def retirada(dia: date, insumo: InsumoDoRelatorio, quantidade: float) -> Lancamento:
    return Lancamento(dia, insumo.id, "saida", None, quantidade)


def saida(dia: date, insumo: InsumoDoRelatorio, quantidade: float, motivo: str) -> Lancamento:
    return Lancamento(dia, insumo.id, "saida", motivo, quantidade)


@pytest.mark.parametrize(
    ("desde", "ate", "agrupar", "esperado"),
    [
        # O primeiro e o último mês cortados no período pedido.
        (
            date(2026, 8, 15),
            date(2026, 10, 10),
            "mes",
            [
                (date(2026, 8, 15), date(2026, 8, 31), "ago/2026"),
                (date(2026, 9, 1), date(2026, 9, 30), "set/2026"),
                (date(2026, 10, 1), date(2026, 10, 10), "out/2026"),
            ],
        ),
        # Semana de segunda a domingo; 21/10/2026 é uma quarta.
        (
            date(2026, 10, 21),
            date(2026, 11, 3),
            "semana",
            [
                (date(2026, 10, 21), date(2026, 10, 25), "semana de 19/10/2026"),
                (date(2026, 10, 26), date(2026, 11, 1), "semana de 26/10/2026"),
                (date(2026, 11, 2), date(2026, 11, 3), "semana de 02/11/2026"),
            ],
        ),
        (
            date(2026, 12, 31),
            date(2027, 1, 1),
            "dia",
            [
                (date(2026, 12, 31), date(2026, 12, 31), "31/12/2026"),
                (date(2027, 1, 1), date(2027, 1, 1), "01/01/2027"),
            ],
        ),
        (
            date(2026, 2, 1),
            date(2026, 2, 1),
            "mes",
            [(date(2026, 2, 1), date(2026, 2, 1), "fev/2026")],
        ),
    ],
)
def test_periodos_cortados_no_pedido(
    desde: date, ate: date, agrupar: str, esperado: list[tuple[date, date, str]]
) -> None:
    assert periodos(desde, ate, agrupar) == esperado


def test_teto_de_periodos() -> None:
    inicio = date(2025, 1, 1)
    assert len(periodos(inicio, date.fromordinal(inicio.toordinal() + 399), "dia")) == 400
    assert MAXIMO_DE_PERIODOS == 400
    with pytest.raises(MuitosPeriodos, match="401 dias"):
        periodos(inicio, date.fromordinal(inicio.toordinal() + 400), "dia")
    # Por mês, o mesmo intervalo cabe com folga.
    assert len(periodos(inicio, date(2026, 2, 5), "mes")) == 14


def test_consumo_so_da_retirada_para_uso_e_so_dentro_do_mesmo_insumo() -> None:
    lancamentos = [
        retirada(date(2026, 9, 2), UREIA, 100),
        retirada(date(2026, 9, 20), UREIA, 50),
        retirada(date(2026, 9, 21), GLIFOSATO, 4),
        # Descarte e falta da contagem não são consumo: são perda.
        saida(date(2026, 9, 22), UREIA, 30, "descarte"),
        saida(date(2026, 9, 23), UREIA, 5, "inventario"),
        # A sobra da contagem não é compra nem consumo.
        Lancamento(date(2026, 9, 24), UREIA.id, "entrada", "inventario", 7),
    ]

    r = relatorio(lancamentos, INSUMOS, date(2026, 9, 1), date(2026, 9, 30), "mes")

    [setembro] = r.periodos
    # Cada insumo na sua unidade, pelo nome: 150 kg de ureia e 4 L de glifosato, nunca
    # "154" de nada. Em reais, pelo custo médio, sim se somam.
    assert [(c.insumo, c.unidade, c.quantidade, c.valor) for c in setembro.consumo] == [
        ("Glifosato", "L", 4, 100.0),
        ("Ureia", "kg", 150, 450.0),
    ]
    assert setembro.perdas == 105.0  # (30 + 5) kg × R$ 3,00
    assert setembro.gasto == 0
    assert r.total.consumo == setembro.consumo


def test_gasto_das_compras_com_preco_e_quantas_ficaram_de_fora() -> None:
    lancamentos = [
        compra(date(2026, 9, 1), UREIA, 1000, 3.1, fornecedor_id=7, fornecedor="Agro Norte"),
        compra(date(2026, 9, 2), UREIA, 500, 2.9, fornecedor_id=8, fornecedor="Casa do Adubo"),
        compra(date(2026, 9, 3), GLIFOSATO, 20, None, fornecedor_id=7, fornecedor="Agro Norte"),
        compra(date(2026, 9, 4), SAL, 300, 1.5),
    ]

    r = relatorio(lancamentos, INSUMOS, date(2026, 9, 1), date(2026, 9, 30), "mes")

    assert r.total.gasto == 3100 + 1450 + 450
    assert r.total.compras_sem_preco == 1
    assert any("1 compra sem preço" in limitacao for limitacao in r.limitacoes)
    assert [
        (f.fornecedor, f.gasto, f.compras, f.compras_sem_preco) for f in r.total.por_fornecedor
    ] == [
        ("Agro Norte", 3100, 2, 1),
        ("Casa do Adubo", 1450, 1, 0),
        (None, 450, 1, 0),  # a compra sem fornecedor, por último
    ]


def test_totais_por_categoria_batem_com_o_total() -> None:
    lancamentos = [
        compra(date(2026, 9, 1), UREIA, 100, 3.0),
        compra(date(2026, 9, 1), SAL, 100, 2.0),
        retirada(date(2026, 9, 5), UREIA, 10),
        retirada(date(2026, 9, 5), GLIFOSATO, 2),
        retirada(date(2026, 9, 5), SAL, 10),  # sem custo médio: fora do consumo em reais
        saida(date(2026, 9, 6), GLIFOSATO, 1, "descarte"),
        saida(date(2026, 9, 6), SAL, 1, "descarte"),  # sem custo médio: fora das perdas
    ]

    r = relatorio(lancamentos, INSUMOS, date(2026, 9, 1), date(2026, 9, 30), "mes")

    categorias = [(c.categoria, c.gasto, c.consumo, c.perdas) for c in r.total.por_categoria]
    assert categorias == [
        ("Defensivo agrícola", 0, 50.0, 25.0),
        ("Fertilizante", 300.0, 30.0, 0),
        (None, 200.0, 0, 0),  # sem categoria, por último
    ]
    assert sum(c.gasto for c in r.total.por_categoria) == r.total.gasto == 500
    assert sum(c.perdas for c in r.total.por_categoria) == r.total.perdas == 25
    assert r.total.perdas_sem_preco == 1
    texto = " ".join(r.limitacoes)
    assert "custo médio de hoje" in texto
    assert "1 perda de insumo sem preço" in texto


def test_periodo_sem_movimento_aparece_zerado() -> None:
    lancamentos = [retirada(date(2026, 8, 10), UREIA, 10), retirada(date(2026, 10, 10), UREIA, 5)]

    r = relatorio(lancamentos, INSUMOS, date(2026, 8, 1), date(2026, 10, 31), "mes")

    assert [(p.rotulo, p.gasto, p.perdas, len(p.consumo)) for p in r.periodos] == [
        ("ago/2026", 0, 0, 1),
        ("set/2026", 0, 0, 0),
        ("out/2026", 0, 0, 1),
    ]
    assert [c.quantidade for c in r.total.consumo] == [15]


def test_lancamento_fora_do_periodo_nao_entra() -> None:
    # A consulta já recorta, mas a agregação não confia nisso: o que cai fora não soma.
    lancamentos = [retirada(date(2026, 7, 31), UREIA, 10), retirada(date(2026, 8, 1), UREIA, 1)]

    r = relatorio(lancamentos, INSUMOS, date(2026, 8, 1), date(2026, 8, 31), "mes")

    assert [c.quantidade for c in r.total.consumo] == [1]


def test_quantidades_e_reais_arredondados() -> None:
    lancamentos = [
        retirada(date(2026, 9, 1), UREIA, 0.1),
        retirada(date(2026, 9, 1), UREIA, 0.2),
        compra(date(2026, 9, 1), UREIA, 0.1, 0.1),
        compra(date(2026, 9, 1), UREIA, 0.2, 0.1),
    ]

    r = relatorio(lancamentos, INSUMOS, date(2026, 9, 1), date(2026, 9, 1), "dia")

    # 0,1 + 0,2 no float é 0,30000000000000004.
    assert r.total.consumo[0].quantidade == 0.3
    assert r.total.gasto == 0.03


def _lancamentos_de_todo_tipo(desde: date, ate: date) -> list[Lancamento]:
    """De tudo um pouco, em todos os dias de uma semana antes de `desde` a uma depois de
    `ate` (as pontas e as viradas de mês e de semana entram), fora de ordem."""
    sorteio = random.Random(7)  # noqa: S311 (fixo, para se repetir; não é segredo)
    lancamentos = []
    for dia in range(desde.toordinal() - 7, ate.toordinal() + 8):
        data = date.fromordinal(dia)
        for _ in range(sorteio.randint(0, 3)):
            insumo = sorteio.choice((UREIA, GLIFOSATO, SAL))
            quantidade = sorteio.randint(1, 500) / 10
            lancamentos.append(
                sorteio.choice(
                    (
                        retirada(data, insumo, quantidade),
                        compra(data, insumo, quantidade, sorteio.choice((None, 2.5))),
                        saida(data, insumo, quantidade, sorteio.choice(("descarte", "inventario"))),
                    )
                )
            )
    sorteio.shuffle(lancamentos)
    return lancamentos


@pytest.mark.parametrize(
    ("desde", "ate", "agrupar"),
    [
        (date(2026, 1, 15), date(2026, 12, 3), "mes"),
        (date(2026, 8, 1), date(2026, 8, 31), "mes"),
        (date(2026, 2, 4), date(2026, 6, 30), "semana"),
        (date(2026, 2, 2), date(2026, 3, 1), "semana"),  # de segunda a domingo, inteiras
        (date(2025, 12, 20), date(2026, 3, 10), "dia"),
    ],
)
def test_cada_periodo_soma_so_os_lancamentos_dele(desde: date, ate: date, agrupar: str) -> None:
    # A conta de antes, um período por vez: cada um é o relatório só daquele intervalo.
    lancamentos = _lancamentos_de_todo_tipo(desde, ate)

    r = relatorio(lancamentos, INSUMOS, desde, ate, agrupar)

    esperado = [
        relatorio(lancamentos, INSUMOS, inicio, fim, agrupar).total
        for inicio, fim, _ in periodos(desde, ate, agrupar)
    ]
    assert [Totais(**{c.name: getattr(p, c.name) for c in fields(Totais)}) for p in r.periodos] == (
        esperado
    )
    assert sum(len(p.consumo) for p in r.periodos) > 0


class _DataContada(date):
    """Uma data que conta quantas vezes foi comparada."""

    comparacoes = 0

    def _contar(self) -> None:
        _DataContada.comparacoes += 1

    def __lt__(self, outra: object) -> bool:
        self._contar()
        return super().__lt__(outra)  # type: ignore[operator]

    def __le__(self, outra: object) -> bool:
        self._contar()
        return super().__le__(outra)  # type: ignore[operator]

    def __gt__(self, outra: object) -> bool:
        self._contar()
        return super().__gt__(outra)  # type: ignore[operator]

    def __ge__(self, outra: object) -> bool:
        self._contar()
        return super().__ge__(outra)  # type: ignore[operator]


def test_um_ano_por_dia_nao_compara_cada_lancamento_com_cada_dia() -> None:
    # 365 dias com 20 lançamentos em cada. Comparar cada lançamento com cada dia seriam
    # 365 × 7.300 × 2, 5 milhões de comparações, e com 50 mil lançamentos levava segundos.
    # Conta as comparações das datas, e não o tempo, que varia com a máquina: separar cada
    # lançamento no seu dia custa umas dezenas por lançamento (ordenar e achar o dia).
    desde, ate = date(2025, 1, 1), date(2025, 12, 31)
    lancamentos = [
        retirada(_DataContada.fromordinal(dia), UREIA, 1)
        for dia in range(desde.toordinal(), ate.toordinal() + 1)
        for _ in range(20)
    ]
    _DataContada.comparacoes = 0

    r = relatorio(lancamentos, INSUMOS, desde, ate, "dia")

    assert len(r.periodos) == 365
    assert r.total.consumo[0].quantidade == 7300
    assert _DataContada.comparacoes < 50 * len(lancamentos)


def test_nomes_na_ordem_da_lista_de_insumos() -> None:
    # Sem diferenciar maiúsculas nem acento, como a busca: pelo código do caractere, "Zinco"
    # viria antes de "adubo", e "Ácido bórico" depois de todos.
    zinco = InsumoDoRelatorio(11, "Zinco", "kg", 21, "Zinco quelatado", custo_medio=None)
    adubo = InsumoDoRelatorio(12, "adubo", "kg", 22, "adubos", custo_medio=None)
    acido = InsumoDoRelatorio(13, "Ácido bórico", "kg", 23, "Ácidos", custo_medio=None)
    insumos = {i.id: i for i in (zinco, adubo, acido)}
    dia = date(2026, 9, 1)
    lancamentos = [
        compra(dia, zinco, 1, 2.0, fornecedor_id=1, fornecedor="Zé Insumos"),
        compra(dia, adubo, 1, 2.0, fornecedor_id=2, fornecedor="agro Norte"),
        compra(dia, acido, 1, 2.0, fornecedor_id=3, fornecedor="Água Boa"),
        *(retirada(dia, insumo, 1) for insumo in (zinco, adubo, acido)),
    ]

    r = relatorio(lancamentos, insumos, dia, dia, "dia")

    assert [c.insumo for c in r.total.consumo] == ["Ácido bórico", "adubo", "Zinco"]
    assert [c.categoria for c in r.total.por_categoria] == ["Ácidos", "adubos", "Zinco quelatado"]
    fornecedores = [f.fornecedor for f in r.total.por_fornecedor]
    assert fornecedores == ["agro Norte", "Água Boa", "Zé Insumos"]
    assert r.limitacoes[0] == (
        "Consumo sem valor em reais (insumo sem compra com preço): Ácido bórico, adubo, Zinco."
    )


@pytest.mark.parametrize(
    ("desde", "ate", "agrupar"),
    [
        (date(9999, 12, 1), date(9999, 12, 31), "mes"),
        (date(9999, 12, 27), date(9999, 12, 31), "semana"),
        (date(9999, 12, 31), date(9999, 12, 31), "dia"),
        (date(1, 1, 1), date(1, 3, 1), "mes"),
        (date(1899, 12, 31), date(1900, 1, 1), "dia"),
    ],
)
def test_datas_fora_da_faixa(desde: date, ate: date, agrupar: str) -> None:
    # Nas pontas do `date`, o mês, a semana ou o dia seguinte não existem.
    with pytest.raises(DataForaDaFaixa, match="01/01/1900 a 31/12/2999"):
        periodos(desde, ate, agrupar)
    assert periodos(DATA_MAXIMA, DATA_MAXIMA, agrupar)[-1][1] == DATA_MAXIMA
    assert periodos(DATA_MINIMA, DATA_MINIMA, agrupar)[0][0] == DATA_MINIMA
