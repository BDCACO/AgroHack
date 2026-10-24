"""O relatório por período (mês, semana ou dia): consumo, gasto, perdas e os totais por
categoria e por fornecedor. Primeiro a agregação pura, sem banco; depois a rota."""

from datetime import date

import pytest

from app.domain.relatorio_por_periodo import (
    MAXIMO_DE_PERIODOS,
    InsumoDoRelatorio,
    Lancamento,
    MuitosPeriodos,
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
