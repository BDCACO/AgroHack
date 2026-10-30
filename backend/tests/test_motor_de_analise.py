"""Motor de análise: regras de estoque e análise de consumo, sem banco e com dados
sintéticos. As contas esperadas estão feitas à mão nos comentários."""

from datetime import date, timedelta

import pytest

from app.analysis.consumo import analisar
from app.domain.estoque import (
    Descarte,
    Encomenda,
    Entrada,
    Insumo,
    Lote,
    Retirada,
    alerta_estoque_minimo,
    alertas_de_validade,
    custo_medio,
    dinheiro_legivel,
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


def test_estoque_minimo_na_entressafra_fica_gravidade_baixa() -> None:
    insumo = Insumo("Ureia", "kg", estoque_atual=5, estoque_minimo=10)

    normal = alerta_estoque_minimo(insumo)
    na_entressafra = alerta_estoque_minimo(insumo, entressafra=True)

    assert normal is not None
    assert normal.gravidade == "media"
    assert na_entressafra is not None
    assert na_entressafra.gravidade == "baixa"
    assert "entressafra" in na_entressafra.justificativa.lower()


def test_consumo_na_entressafra_ignora_o_consumo_alto_da_safra_no_mesmo_historico() -> None:
    # Setembro a março é safra; abril é entressafra. A janela de 90 dias antes de
    # 15/abr vai de 16/jan a 15/abr: 75 dias de safra (com retirada pesada) e 15 dias
    # de entressafra (sem nenhuma). Sem separar por período, a média dos 90 dias
    # diria ~8,3 kg/dia; separando, só entra a entressafra: zero.
    ref = date(2026, 4, 15)
    insumo = Insumo("Ureia", "kg", estoque_atual=50, estoque_minimo=5, prazo_reposicao_dias=15)
    retiradas = [Retirada(date(2026, 1, 16) + timedelta(days=i), 10) for i in range(75)]

    analise = analisar(
        insumo,
        retiradas,
        registros_desde=ref - timedelta(days=119),
        referencia=ref,
        meses_de_safra=[9, 10, 11, 12, 1, 2, 3],
    )

    assert analise.consumo_diario == 0.0
    assert analise.reposicao is None
    assert "risco_de_falta" not in [a.tipo for a in analise.alertas]


def test_sem_meses_de_safra_consumo_usa_a_janela_inteira_como_antes() -> None:
    ref = date(2026, 4, 15)
    insumo = Insumo("Ureia", "kg", estoque_atual=50, estoque_minimo=5, prazo_reposicao_dias=15)
    retiradas = [date(2026, 1, 16) + timedelta(days=i) for i in range(75)]
    retiradas = [Retirada(d, 10) for d in retiradas]

    analise = analisar(insumo, retiradas, registros_desde=ref - timedelta(days=119), referencia=ref)

    assert analise.consumo_diario == pytest.approx(750 / 90)


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


def test_descarte_sai_primeiro_do_lote_vencido() -> None:
    vencido, novo = antes(60), REF + timedelta(days=300)
    entradas = [Entrada(antes(120), 10, vencido), Entrada(antes(70), 10, novo)]
    retiradas = [Retirada(antes(40), 3)]

    lotes = lotes_em_estoque(entradas, retiradas, descartes=[Descarte(antes(5), 10)])

    # A retirada saiu do novo (o outro já tinha vencido); o descarte levou o vencido.
    assert lotes == [Lote(7, novo)]


def test_dinheiro_legivel_no_formato_brasileiro() -> None:
    assert dinheiro_legivel(1234.5) == "R$ 1.234,50"
    assert dinheiro_legivel(0.004) == "R$ 0,00"
    assert dinheiro_legivel(2_000_000) == "R$ 2.000.000,00"


def test_custo_medio_pondera_pela_quantidade_e_ignora_compra_sem_preco() -> None:
    entradas = [
        Entrada(antes(60), 1000, valor_unitario=3.0),
        Entrada(antes(30), 500, valor_unitario=3.6),
        Entrada(antes(10), 200),  # sem preço: fica fora da conta
    ]

    # (1000 × 3,00 + 500 × 3,60) / 1500 = 4800 / 1500 = 3,20
    assert custo_medio(entradas) == pytest.approx(3.2)
    assert custo_medio([Entrada(antes(5), 10)]) is None
    assert custo_medio([]) is None


def test_custo_medio_e_em_centavos_para_a_conta_bater_com_o_texto() -> None:
    # 400 kg a R$ 3,00 e 300 kg a R$ 3,37 dão R$ 3,1585714...: a tela mostra R$ 3,16, e a
    # conta em reais tem de ser feita com os mesmos R$ 3,16 que o produtor lê.
    entradas = [
        Entrada(antes(9), 400, valor_unitario=3),
        Entrada(antes(5), 300, valor_unitario=3.37),
    ]

    assert custo_medio(entradas) == 3.16


def test_validade_com_custo_medio_diz_quanto_dinheiro_esta_em_jogo() -> None:
    lotes = [Lote(20, REF + timedelta(days=10)), Lote(10, antes(5))]

    alertas = alertas_de_validade(lotes, REF, "kg", custo_medio=3.2)

    # O começo é o mesmo de sem preço; o valor vem no fim: 10 × 3,20 e 20 × 3,20.
    assert [(a.tipo, a.justificativa, a.valor) for a in alertas] == [
        (
            "vencido",
            "10 kg vencidos em 25/06/2026, há 5 dias. Pelo custo médio de R$ 3,20/kg, são "
            "cerca de R$ 32,00.",
            pytest.approx(32),
        ),
        (
            "vencimento_proximo",
            "20 kg vencem em 10/07/2026 (em 10 dias). Pelo custo médio de R$ 3,20/kg, são "
            "cerca de R$ 64,00.",
            pytest.approx(64),
        ),
    ]
    assert all(a.valor is None for a in alertas_de_validade(lotes, REF, "kg"))


def test_excesso_com_custo_medio_mostra_o_capital_parado() -> None:
    insumo = Insumo("Herbicida", "L", estoque_atual=500, estoque_minimo=10)

    analise = analisar(
        insumo, diarias(1, 120), registros_desde=DESDE_120_DIAS, referencia=REF, custo_medio=25
    )

    # 1 L/dia: 180 dias de consumo são 180 L; os 320 L além disso, a R$ 25,00, são R$ 8.000.
    [excesso] = analise.alertas
    assert excesso.valor == pytest.approx(8000)
    assert excesso.justificativa == (
        "No ritmo atual (1 L/dia), o estoque dura cerca de 500 dias; acima de 180 dias, é "
        "capital parado. Pelo custo médio de R$ 25,00/L, os 320 L além de 180 dias de consumo "
        "são cerca de R$ 8.000,00."
    )


def test_alertas_sem_dinheiro_envolvido_nao_tem_valor() -> None:
    insumo = Insumo("Ureia", "kg", estoque_atual=20, estoque_minimo=30, prazo_reposicao_dias=15)

    analise = analisar(
        insumo, diarias(2, 120), registros_desde=DESDE_120_DIAS, referencia=REF, custo_medio=3
    )

    assert {a.tipo for a in analise.alertas} == {"risco_de_falta", "abaixo_do_minimo"}
    assert all(a.valor is None for a in analise.alertas)


def ureia(**cadastro: float) -> Insumo:
    """2 kg/dia, 20 kg em estoque, mínimo de 10 e entrega em 15 dias: a conta dá 70 kg."""
    return Insumo("Ureia", "kg", 20, estoque_minimo=10, prazo_reposicao_dias=15, **cadastro)


def repor(insumo: Insumo, custo_medio: float | None = None, a_caminho: list[Encomenda] = ()):
    return analisar(
        insumo,
        diarias(2, 120),
        registros_desde=DESDE_120_DIAS,
        referencia=REF,
        custo_medio=custo_medio,
        a_caminho=a_caminho,
    )


def test_reposicao_arredonda_para_cima_em_embalagens_fechadas() -> None:
    analise = repor(ureia(embalagem=50))

    # 70 kg não fecham saco de 50: são 2 sacos, 100 kg.
    assert analise.reposicao.quantidade == pytest.approx(100)
    assert analise.reposicao.justificativa == (
        "Pedir hoje 2 embalagens de 50 kg (100 kg): com entrega em 15 dias, cobre 30 dias de "
        "consumo a 2 kg/dia, mantendo o mínimo de 10 kg. A conta dá 70 kg; a quantidade foi "
        "arredondada para cima em embalagens fechadas."
    )
    assert repor(ureia(embalagem=70)).reposicao.justificativa.startswith(
        "Pedir hoje 1 embalagem de 70 kg (70 kg): com entrega"
    )


def test_reposicao_respeita_o_pedido_minimo_antes_de_arredondar() -> None:
    so_minimo = repor(ureia(pedido_minimo=200, embalagem=50)).reposicao
    os_dois = repor(ureia(pedido_minimo=210, embalagem=50)).reposicao

    assert so_minimo.quantidade == pytest.approx(200)
    assert so_minimo.justificativa.endswith(
        "A conta dá 70 kg; a quantidade subiu para o pedido mínimo de 200 kg."
    )
    # 210 de mínimo em sacos de 50: 5 sacos, 250 kg.
    assert os_dois.quantidade == pytest.approx(250)
    assert os_dois.justificativa.endswith(
        "A conta dá 70 kg; a quantidade subiu para o pedido mínimo de 210 kg e foi "
        "arredondada para cima em embalagens fechadas."
    )
    # Pedido mínimo abaixo da conta não muda nada.
    assert repor(ureia(pedido_minimo=50)).reposicao.quantidade == pytest.approx(70)


def test_reposicao_com_custo_medio_estima_o_custo_da_compra() -> None:
    reposicao = repor(ureia(embalagem=50), custo_medio=3.2).reposicao

    assert reposicao.custo_estimado == pytest.approx(320)
    assert reposicao.justificativa.endswith(
        "Pelo custo médio de R$ 3,20/kg, a compra fica em cerca de R$ 320,00."
    )
    assert repor(ureia()).reposicao.custo_estimado is None


def test_limitacao_da_reposicao_diz_so_o_que_falta() -> None:
    def sobre_a_quantidade(analise) -> list[str]:
        return [t for t in analise.limitacoes if t.startswith("A quantidade sugerida")]

    assert sobre_a_quantidade(repor(ureia())) == [
        "A quantidade sugerida não considera embalagem nem preço."
    ]
    assert sobre_a_quantidade(repor(ureia(embalagem=50))) == [
        "A quantidade sugerida não considera preço."
    ]
    assert sobre_a_quantidade(repor(ureia(), custo_medio=3)) == [
        "A quantidade sugerida não considera embalagem."
    ]
    assert sobre_a_quantidade(repor(ureia(embalagem=50), custo_medio=3)) == []


def risco(analise):
    return next(a for a in analise.alertas if a.tipo == "risco_de_falta")


def test_reposicao_desconta_o_que_ja_foi_pedido() -> None:
    analise = repor(ureia(), a_caminho=[Encomenda(70, REF + timedelta(days=5))])

    # Com os 70 kg a caminho, a posição é de 90 kg: (90 - 10) / 2 = 40 dias acima do
    # mínimo, menos 15 de entrega → pedir em 25 dias, e não hoje. Restam 40 kg no pedido,
    # 10 na chegada, e a conta cobre 30 × 2 kg.
    reposicao = analise.reposicao
    assert (reposicao.pedir_hoje, reposicao.pedir_em) == (False, REF + timedelta(days=25))
    assert reposicao.quantidade == pytest.approx(60)
    assert "Desconta os 70 kg já pedidos e ainda não recebidos." in reposicao.justificativa
    # Sem pedido a caminho, a mesma conta manda pedir hoje, e o texto não fala em pedido.
    sem_pedido = repor(ureia()).reposicao
    assert sem_pedido.pedir_hoje is True
    assert "pedidos" not in sem_pedido.justificativa


def test_desconto_do_pedido_vem_antes_do_custo_no_texto() -> None:
    reposicao = repor(
        ureia(embalagem=50), custo_medio=3, a_caminho=[Encomenda(10, REF + timedelta(days=2))]
    ).reposicao

    assert reposicao.justificativa.endswith(
        "Desconta os 10 kg já pedidos e ainda não recebidos. Pelo custo médio de R$ 3,00/kg, "
        "a compra fica em cerca de R$ 300,00."
    )


def test_pedido_que_chega_antes_de_acabar_baixa_a_gravidade_do_risco() -> None:
    analise = repor(ureia(), a_caminho=[Encomenda(70, REF + timedelta(days=5))])

    # O estoque físico continua durando 10 dias: o alerta fica, mas com o pedido chegando
    # no dia 5 ele passa a durar (20 + 70) / 2 = 45 dias.
    alerta = risco(analise)
    assert alerta.gravidade == "media"
    assert alerta.justificativa == (
        "No ritmo atual (2 kg/dia), o estoque dura cerca de 10 dias, menos que o prazo de "
        "reposição de 15 dias. Já foram pedidos 70 kg. Chegam 70 kg até 05/07/2026, antes de o "
        "estoque acabar, e com eles ele dura cerca de 45 dias: confira a entrega."
    )


def test_pedido_que_chega_a_tempo_mas_nao_basta_continua_urgente() -> None:
    analise = repor(ureia(), a_caminho=[Encomenda(5, REF + timedelta(days=5))])

    # (20 + 5) / 2 = 12,5 dias, ainda menos que os 15 de entrega.
    alerta = risco(analise)
    assert alerta.gravidade == "alta"
    assert alerta.justificativa.endswith(
        "Chegam 5 kg até 05/07/2026, antes de o estoque acabar, mas com eles ele dura só cerca "
        "de 12 dias."
    )
    assert analise.reposicao.pedir_hoje is True


def test_pedido_que_chega_depois_de_acabar_continua_urgente() -> None:
    analise = repor(ureia(), a_caminho=[Encomenda(70, REF + timedelta(days=12))])

    alerta = risco(analise)
    assert alerta.gravidade == "alta"
    assert alerta.justificativa.endswith(
        "Já foram pedidos 70 kg. 70 kg só chegam em 12/07/2026, depois de o estoque acabar."
    )


def test_pedido_atrasado_continua_urgente_e_pede_para_cobrar() -> None:
    analise = repor(ureia(), a_caminho=[Encomenda(70, REF - timedelta(days=1))])

    alerta = risco(analise)
    assert alerta.gravidade == "alta"
    assert alerta.justificativa.endswith(
        "70 kg estavam previstos para 29/06/2026 e ainda não chegaram: cobre a revenda."
    )


def test_pedido_sem_data_prevista_continua_urgente_e_vira_limitacao() -> None:
    analise = repor(ureia(), a_caminho=[Encomenda(70)])

    alerta = risco(analise)
    assert alerta.gravidade == "alta"
    assert alerta.justificativa.endswith("70 kg não têm data prevista de chegada.")
    assert (
        "Pedido a caminho sem data prevista de chegada: a reposição o desconta, mas não dá "
        "para saber se ele chega antes de o estoque acabar."
    ) in analise.limitacoes
    # A reposição o desconta mesmo assim: o produto foi pedido.
    assert analise.reposicao.pedir_hoje is False
    # Com data, a limitação some.
    com_data = repor(ureia(), a_caminho=[Encomenda(70, REF + timedelta(days=5))])
    assert not any("sem data prevista" in t for t in com_data.limitacoes)
