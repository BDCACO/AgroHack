"""Motor de análise: regras de estoque e análise de consumo, sem banco e com dados
sintéticos. As contas esperadas estão feitas à mão nos comentários."""

from datetime import date, timedelta

import pytest

from app.analysis.consumo import analisar
from app.domain.estoque import (
    Entrada,
    Insumo,
    Lote,
    Retirada,
    alerta_estoque_minimo,
    alertas_de_validade,
    lotes_em_estoque,
    quantidade_legivel,
)

REF = date(2026, 6, 30)
DESDE_120_DIAS = REF - timedelta(days=119)


def diarias(quantidade: float, dias: int) -> list[Retirada]:
    return [Retirada(REF - timedelta(days=i), quantidade) for i in range(dias)]


def antes(dias: int) -> date:
    return REF - timedelta(days=dias)


def test_risco_de_falta_pede_compra_hoje_e_ignora_retiradas_fora_do_periodo() -> None:
    insumo = Insumo("Ureia", "kg", estoque_atual=20, estoque_minimo=10, prazo_reposicao_dias=15)
    fora = [Retirada(REF + timedelta(days=1), 1000), Retirada(antes(200), 1000)]

    analise = analisar(
        insumo,
        diarias(2, 120) + fora,
        registros_desde=DESDE_120_DIAS,
        referencia=REF,
        lotes=[Lote(5, REF + timedelta(days=10))],
    )

    # 2 kg/dia → 20 kg duram 10 dias, menos que os 15 de entrega.
    assert analise.consumo_diario == pytest.approx(2)
    assert analise.cobertura_dias == pytest.approx(10)
    assert [a.tipo for a in analise.alertas] == ["risco_de_falta", "vencimento_proximo"]
    # Chega com zero: 10 de mínimo + 30 dias × 2 kg.
    assert analise.reposicao is not None
    assert analise.reposicao.pedir_em == REF
    assert analise.reposicao.quantidade == pytest.approx(70)
    assert analise.reposicao.justificativa.startswith("Pedir hoje 70 kg")


def test_reposicao_futura_pede_quando_a_folga_cobre_o_prazo() -> None:
    insumo = Insumo("Calcário", "kg", estoque_atual=100, estoque_minimo=10, prazo_reposicao_dias=15)

    analise = analisar(insumo, diarias(2, 120), registros_desde=DESDE_120_DIAS, referencia=REF)

    # (100 - 10) / 2 = 45 dias acima do mínimo, menos 15 de entrega → pedir em 30 dias,
    # quando restam 40 kg; na chegada sobram 10 (o mínimo) e o pedido cobre 30 × 2 kg.
    assert analise.alertas == []
    assert analise.reposicao is not None
    assert analise.reposicao.pedir_em == REF + timedelta(days=30)
    assert analise.reposicao.quantidade == pytest.approx(60)


def test_excesso_e_limitacoes_de_cadastro_incompleto() -> None:
    insumo = Insumo("Herbicida", "L", estoque_atual=500)

    analise = analisar(insumo, diarias(1, 120), registros_desde=DESDE_120_DIAS, referencia=REF)

    assert [(a.tipo, a.gravidade) for a in analise.alertas] == [("excesso", "baixa")]
    assert analise.reposicao is None
    limitacoes = " ".join(analise.limitacoes)
    assert "Estoque mínimo não cadastrado" in limitacoes
    assert "assumidos 15 dias" in limitacoes


def test_consumo_infimo_nao_estoura_a_data_da_reposicao() -> None:
    insumo = Insumo("Calcário", "t", estoque_atual=1_000_000)

    analise = analisar(
        insumo, [Retirada(antes(10), 0.5)], registros_desde=DESDE_120_DIAS, referencia=REF
    )

    assert [a.tipo for a in analise.alertas] == ["excesso"]
    assert analise.reposicao is None


def test_historico_curto_nao_estima_consumo() -> None:
    insumo = Insumo("Ureia", "kg", estoque_atual=20, estoque_minimo=10)

    analise = analisar(insumo, diarias(2, 10), registros_desde=antes(9), referencia=REF)

    assert analise.consumo_diario is None
    assert analise.reposicao is None
    assert any("Só 10 dias de registros" in texto for texto in analise.limitacoes)


def test_baixa_movimentacao() -> None:
    insumo = Insumo("Fungicida", "L", estoque_atual=50)

    com_retirada_antiga = analisar(
        insumo, [Retirada(antes(100), 10)], registros_desde=DESDE_120_DIAS, referencia=REF
    )
    sem_retirada = analisar(insumo, [], registros_desde=DESDE_120_DIAS, referencia=REF)
    historico_curto = analisar(insumo, [], registros_desde=antes(29), referencia=REF)

    assert [a.justificativa for a in com_retirada_antiga.alertas] == [
        "50 L sem retiradas há 100 dias (última em 22/03/2026)."
    ]
    assert com_retirada_antiga.consumo_diario == 0
    assert com_retirada_antiga.reposicao is None
    assert "nenhuma desde o início" in sem_retirada.alertas[0].justificativa
    # 30 dias sem retirada num histórico de 30 dias não prova que o insumo está parado.
    assert historico_curto.alertas == []


def test_consumo_incomum_compara_a_ultima_semana_com_as_anteriores() -> None:
    insumo = Insumo("Adubo", "kg", estoque_atual=1000)
    semanais = [Retirada(antes(7 * semana + 3), 10) for semana in range(17)]

    estavel = analisar(insumo, semanais, registros_desde=DESDE_120_DIAS, referencia=REF)
    pico = analisar(
        insumo, [*semanais, Retirada(antes(1), 30)], registros_desde=DESDE_120_DIAS, referencia=REF
    )
    curto = analisar(insumo, semanais, registros_desde=antes(19), referencia=REF)

    assert "consumo_incomum" not in [a.tipo for a in estavel.alertas]
    assert [a.justificativa for a in pico.alertas if a.tipo == "consumo_incomum"] == [
        "Saíram 40 kg nos últimos 7 dias; nas 12 semanas anteriores a média foi de "
        "10 kg por semana (desvio de 0 kg)."
    ]
    assert any("consumo incomum não avaliado" in texto for texto in curto.limitacoes)


def test_estoque_minimo() -> None:
    abaixo = alerta_estoque_minimo(Insumo("Ureia", "kg", estoque_atual=5, estoque_minimo=10))
    zerado = alerta_estoque_minimo(Insumo("Ureia", "kg", estoque_atual=0, estoque_minimo=10))

    assert abaixo is not None
    assert (abaixo.gravidade, abaixo.justificativa) == (
        "media",
        "Estoque atual de 5 kg, abaixo do mínimo de 10 kg.",
    )
    assert zerado is not None
    assert zerado.gravidade == "alta"
    assert alerta_estoque_minimo(Insumo("Ureia", "kg", estoque_atual=10, estoque_minimo=10)) is None
    assert alerta_estoque_minimo(Insumo("Ureia", "kg", estoque_atual=0)) is None


def test_validade() -> None:
    lotes = [
        Lote(30, REF + timedelta(days=100)),
        Lote(20, REF + timedelta(days=10)),
        Lote(10, antes(5)),
        Lote(0, antes(1)),  # lote já consumido não gera alerta
    ]

    alertas = alertas_de_validade(lotes, REF, "kg")

    assert [(a.tipo, a.gravidade, a.justificativa) for a in alertas] == [
        ("vencido", "alta", "10 kg vencidos em 25/06/2026, há 5 dias."),
        ("vencimento_proximo", "media", "20 kg vencem em 10/07/2026 (em 10 dias)."),
    ]


def test_quantidade_legivel_no_formato_brasileiro() -> None:
    assert quantidade_legivel(1234.5, "kg") == "1.234,5 kg"
    assert quantidade_legivel(0.03, "L") == "0,03 L"
    assert quantidade_legivel(12, "sc") == "12 sc"


def test_lotes_em_estoque_usa_primeiro_o_que_vence_primeiro_entre_os_que_ja_chegaram() -> None:
    dezembro, agosto = date(2026, 12, 1), date(2026, 8, 1)
    entradas = [
        Entrada(antes(10), 5),  # sem validade: vai para o fim da fila e não vira lote
        Entrada(antes(9), 10, dezembro),
        Entrada(antes(7), 10, agosto),
        Entrada(antes(1), 5, agosto),
    ]
    retiradas = [
        # Só o lote de dezembro tinha chegado: sai dele, mesmo vencendo depois.
        Retirada(antes(8), 4),
        # Agora o de agosto vence primeiro.
        Retirada(antes(6), 8),
        # No mesmo dia, a entrada conta antes da retirada.
        Retirada(antes(1), 3),
    ]

    assert lotes_em_estoque(entradas, retiradas) == [Lote(6, dezembro), Lote(4, agosto)]


def test_retirada_nao_sai_de_lote_que_ja_tinha_vencido() -> None:
    # Ninguém aplica produto vencido: depois da validade, o lote fica parado na
    # prateleira até ser descartado, e as retiradas saem do lote bom.
    vencido, novo = antes(60), REF + timedelta(days=300)
    entradas = [Entrada(antes(120), 10, vencido), Entrada(antes(70), 10, novo)]
    retiradas = [Retirada(antes(50 - 7 * i), 1) for i in range(8)]

    assert lotes_em_estoque(entradas, retiradas) == [Lote(10, vencido), Lote(2, novo)]


def test_retirada_no_dia_da_validade_ainda_usa_o_lote() -> None:
    validade = antes(10)
    entradas = [Entrada(antes(30), 5, validade), Entrada(antes(30), 5, REF + timedelta(days=90))]

    lotes = lotes_em_estoque(entradas, [Retirada(validade, 2)])

    assert lotes == [Lote(3, validade), Lote(5, REF + timedelta(days=90))]


def test_sem_lote_valido_a_retirada_sai_do_vencido() -> None:
    # Só sobrou produto vencido e houve retirada: ou foi usado vencido, ou falta
    # registro. Tirar do vencido mantém a soma dos lotes igual ao estoque.
    vencido = antes(60)
    lotes = lotes_em_estoque([Entrada(antes(120), 10, vencido)], [Retirada(antes(30), 4)])

    assert lotes == [Lote(6, vencido)]
