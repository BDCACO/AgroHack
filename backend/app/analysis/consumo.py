"""Análise de um insumo a partir das retiradas: ritmo de consumo, cobertura, alertas e
reposição — cada resultado com a justificativa da conta e as limitações dos dados.

Média e desvio-padrão com `statistics`, sem Pandas: o produtor precisa entender a conta
por trás de cada alerta, e as retiradas de uma propriedade cabem numa lista.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import mean, stdev

from app.domain.estoque import (
    Alerta,
    Encomenda,
    Gravidade,
    Insumo,
    Lote,
    Retirada,
    alerta_estoque_minimo,
    alertas_de_validade,
    dias_legivel,
    dinheiro_legivel,
    quantidade_legivel,
    valor_pelo_custo_medio,
)

JANELA_CONSUMO_DIAS = 90
HISTORICO_MINIMO_DIAS = 14
# Conservador: supor prazo longo antecipa o alerta em vez de atrasá-lo.
PRAZO_REPOSICAO_PADRAO_DIAS = 15
# A sugestão de compra cobre este tanto de consumo depois que o pedido chega.
HORIZONTE_COMPRA_DIAS = 30
COBERTURA_EXCESSO_DIAS = 180
DIAS_SEM_RETIRADA = 60
SEMANAS_COMPARADAS = 12
SEMANAS_MINIMAS = 4

_ORDEM_GRAVIDADE = {"alta": 0, "media": 1, "baixa": 2}


@dataclass(frozen=True)
class Reposicao:
    pedir_em: date
    # Inteira, ou o múltiplo da embalagem (que pode ser fracionada, como o frasco de 0,5 L).
    quantidade: float
    justificativa: str
    # Decidido aqui, na data de referência da análise (Rondônia): a tela e o relatório
    # não comparam datas cada um com o seu relógio.
    pedir_hoje: bool
    # Quantidade × custo médio; None sem preço nas compras.
    custo_estimado: float | None = None


@dataclass(frozen=True)
class Analise:
    consumo_diario: float | None
    cobertura_dias: float | None
    alertas: list[Alerta]
    reposicao: Reposicao | None
    limitacoes: list[str]


def analisar(
    insumo: Insumo,
    retiradas: Iterable[Retirada],
    *,
    registros_desde: date,
    referencia: date,
    lotes: Iterable[Lote] = (),
    custo_medio: float | None = None,
    a_caminho: Iterable[Encomenda] = (),
    meses_de_safra: Iterable[int] = (),
) -> Analise:
    """Analisa o insumo na data de referência.

    `registros_desde` é a data a partir da qual as retiradas estão completas: é o que
    separa "não houve consumo" de "não havia registro". `custo_medio` (R$ por unidade) é
    opcional: com ele, os alertas e a reposição dizem também quanto dinheiro está em jogo.
    `a_caminho` é o que já foi pedido e não chegou: a reposição o desconta, para não mandar
    comprar de novo, e o alerta de falta diz se ele chega antes de o estoque acabar.
    `meses_de_safra` (1 a 12) é o calendário da fazenda inteira; vazio desliga a
    sazonalidade e a análise sai como sempre saiu.
    """
    a_caminho = [e for e in a_caminho if e.quantidade > 0]
    meses_de_safra = set(meses_de_safra)
    entressafra = bool(meses_de_safra) and referencia.month not in meses_de_safra
    alertas = alertas_de_validade(lotes, referencia, insumo.unidade, custo_medio)
    if (alerta := alerta_estoque_minimo(insumo, entressafra)) is not None:
        alertas.append(alerta)
    limitacoes = []
    if insumo.estoque_minimo is None:
        limitacoes.append(
            "Estoque mínimo não cadastrado: sem alerta de mínimo, e a reposição não "
            "guarda margem de segurança."
        )
    if insumo.estoque_atual < 0:
        limitacoes.append("Estoque atual negativo: há entrada ou saída faltando nos registros.")
    if any(e.previsto_para is None for e in a_caminho):
        limitacoes.append(
            "Pedido a caminho sem data prevista de chegada: a reposição o desconta, mas não dá "
            "para saber se ele chega antes de o estoque acabar."
        )

    retiradas = [r for r in retiradas if registros_desde <= r.data <= referencia]
    dias_historico = (referencia - registros_desde).days + 1

    def resultado(
        consumo: float | None = None,
        cobertura: float | None = None,
        reposicao: Reposicao | None = None,
    ) -> Analise:
        alertas.sort(key=lambda a: _ORDEM_GRAVIDADE[a.gravidade])
        return Analise(consumo, cobertura, alertas, reposicao, limitacoes)

    if dias_historico < HISTORICO_MINIMO_DIAS:
        limitacoes.append(
            f"Só {dias_legivel(dias_historico)} de registros (mínimo de "
            f"{HISTORICO_MINIMO_DIAS}): consumo, cobertura e reposição não estimados."
        )
        return resultado()

    if (alerta := _baixa_movimentacao(insumo, retiradas, dias_historico, referencia)) is not None:
        alertas.append(alerta)
    alertas.extend(_consumo_incomum(insumo, retiradas, dias_historico, referencia, limitacoes))

    dias_janela = min(JANELA_CONSUMO_DIAS, dias_historico)
    inicio_janela = referencia - timedelta(days=dias_janela - 1)
    if meses_de_safra:
        # Só os dias do mesmo período (safra ou entressafra) que hoje: misturar os dois
        # numa média só traria para a entressafra o ritmo alto da safra (e vice-versa).
        # O próprio dia de referência está sempre na janela e é desse período, então
        # sempre há ao menos um dia para dividir.
        dias_do_periodo = sum(
            1
            for i in range(dias_janela)
            if ((inicio_janela + timedelta(days=i)).month in meses_de_safra) != entressafra
        )
        consumo = (
            sum(
                r.quantidade
                for r in retiradas
                if r.data >= inicio_janela and (r.data.month in meses_de_safra) != entressafra
            )
            / dias_do_periodo
        )
        periodo = "entressafra" if entressafra else "safra"
        limitacoes.append(
            f"Consumo é a média dos dias de {periodo} nos últimos {dias_legivel(dias_janela)}: "
            "não antecipa mudanças de manejo dentro da mesma época."
        )
    else:
        consumo = sum(r.quantidade for r in retiradas if r.data >= inicio_janela) / dias_janela
        limitacoes.append(
            f"Consumo é a média dos últimos {dias_legivel(dias_janela)}: não antecipa a "
            "sazonalidade da safra nem mudanças de manejo."
        )
    if consumo == 0:
        return resultado(consumo=0.0)

    prazo = insumo.prazo_reposicao_dias
    if prazo is None:
        prazo = PRAZO_REPOSICAO_PADRAO_DIAS
        limitacoes.append(f"Prazo de reposição não cadastrado: assumidos {prazo} dias.")

    cobertura = max(insumo.estoque_atual, 0) / consumo
    ritmo = f"{quantidade_legivel(consumo, insumo.unidade)}/dia"
    if cobertura <= prazo:
        texto = (
            f"No ritmo atual ({ritmo}), o estoque dura cerca de {dias_legivel(cobertura)}"
            f", menos que o prazo de reposição de {dias_legivel(prazo)}."
        )
        gravidade: Gravidade = "alta"
        if a_caminho:
            # O estoque físico continua baixo, e o alerta fica; o pedido a caminho só tira
            # a urgência se chega antes de acabar e, com ele, o estoque passa do prazo.
            gravidade, sobre_o_pedido = _pedido_no_risco(
                insumo, a_caminho, consumo, cobertura, prazo, referencia
            )
            texto += sobre_o_pedido
        alertas.append(Alerta("risco_de_falta", gravidade, texto))
    elif cobertura > COBERTURA_EXCESSO_DIAS:
        texto = (
            f"No ritmo atual ({ritmo}), o estoque dura cerca de {dias_legivel(cobertura)}"
            f"; acima de {COBERTURA_EXCESSO_DIAS} dias, é capital parado."
        )
        valor = None
        if custo_medio is not None:
            # Parado é só o que passa da cobertura aceitável; o resto vai ser usado.
            sobra = insumo.estoque_atual - consumo * COBERTURA_EXCESSO_DIAS
            valor = round(sobra * custo_medio, 2)
            texto += (
                f" {valor_pelo_custo_medio(custo_medio, insumo.unidade)}, os "
                f"{quantidade_legivel(sobra, insumo.unidade)} além de "
                f"{COBERTURA_EXCESSO_DIAS} dias de consumo são cerca de "
                f"{dinheiro_legivel(valor)}."
            )
        alertas.append(Alerta("excesso", "baixa", texto, valor))
        # Com excesso não há compra a sugerir — e isso limita a data do pedido a
        # COBERTURA_EXCESSO_DIAS, em vez de séculos à frente com consumo ínfimo.
        return resultado(consumo=consumo, cobertura=cobertura)

    # Só o que de fato falta: pedido mínimo vazio é fornecedor sem mínimo, não falta de dado.
    faltam = [
        nome
        for nome, falta in (("embalagem", insumo.embalagem is None), ("preço", custo_medio is None))
        if falta
    ]
    if faltam:
        limitacoes.append(f"A quantidade sugerida não considera {' nem '.join(faltam)}.")
    em_pedido = round(sum(e.quantidade for e in a_caminho), 3)
    reposicao = _reposicao(insumo, consumo, prazo, referencia, custo_medio, em_pedido)
    return resultado(consumo=consumo, cobertura=cobertura, reposicao=reposicao)


def _baixa_movimentacao(
    insumo: Insumo, retiradas: list[Retirada], dias_historico: int, referencia: date
) -> Alerta | None:
    # Histórico mais curto que o limiar não permite afirmar que o insumo está parado.
    if insumo.estoque_atual <= 0 or dias_historico < DIAS_SEM_RETIRADA:
        return None
    ultima = max((r.data for r in retiradas), default=None)
    parado = (referencia - ultima).days if ultima else dias_historico
    if parado < DIAS_SEM_RETIRADA:
        return None
    detalhe = f"última em {ultima:%d/%m/%Y}" if ultima else "nenhuma desde o início dos registros"
    return Alerta(
        "baixa_movimentacao",
        "baixa",
        f"{quantidade_legivel(insumo.estoque_atual, insumo.unidade)} sem retiradas há "
        f"{dias_legivel(parado)} ({detalhe}).",
    )


def _consumo_incomum(
    insumo: Insumo,
    retiradas: list[Retirada],
    dias_historico: int,
    referencia: date,
    limitacoes: list[str],
) -> list[Alerta]:
    """Compara a última semana com as anteriores. Só olha para cima: consumo baixo
    é assunto de `_baixa_movimentacao`."""
    semanas_anteriores = min(SEMANAS_COMPARADAS, dias_historico // 7 - 1)
    if semanas_anteriores < SEMANAS_MINIMAS:
        limitacoes.append(
            f"Menos de {SEMANAS_MINIMAS} semanas de histórico antes da última: consumo "
            "incomum não avaliado."
        )
        return []

    # Semana 0 = últimos 7 dias. Semana sem retirada conta como zero: houve registro.
    totais = [0.0] * (semanas_anteriores + 1)
    for r in retiradas:
        semana = (referencia - r.data).days // 7
        if semana <= semanas_anteriores:
            totais[semana] += r.quantidade
    atual, anteriores = totais[0], totais[1:]
    media, desvio = mean(anteriores), stdev(anteriores)
    # Dois desvios acima E 50% acima da média: com semanas muito regulares o desvio
    # fica perto de zero, e qualquer oscilação pequena viraria alerta.
    if atual <= media + 2 * desvio or atual <= 1.5 * media:
        return []
    unidade = insumo.unidade
    return [
        Alerta(
            "consumo_incomum",
            "media",
            f"Saíram {quantidade_legivel(atual, unidade)} nos últimos 7 dias; nas "
            f"{semanas_anteriores} semanas anteriores a média foi de "
            f"{quantidade_legivel(media, unidade)} por semana "
            f"(desvio de {quantidade_legivel(desvio, unidade)}).",
        )
    ]


def _pedido_no_risco(
    insumo: Insumo,
    a_caminho: list[Encomenda],
    consumo: float,
    cobertura: float,
    prazo: int,
    referencia: date,
) -> tuple[Gravidade, str]:
    """A gravidade do risco de falta com o pedido a caminho, e a frase que diz por quê."""
    unidade = insumo.unidade

    def total(encomendas: list[Encomenda]) -> str:
        return quantidade_legivel(sum(e.quantidade for e in encomendas), unidade)

    # O último dia com estoque: o que chega até ele evita a falta.
    acaba_em = referencia + timedelta(days=math.floor(cobertura))
    com_data = [e for e in a_caminho if e.previsto_para is not None]
    a_tempo = [e for e in com_data if referencia <= e.previsto_para <= acaba_em]
    # Previsto para antes de hoje e não recebido: a entrega está atrasada.
    atrasados = [e for e in com_data if e.previsto_para < referencia]
    tarde = [e for e in com_data if e.previsto_para > acaba_em]
    sem_data = [e for e in a_caminho if e.previsto_para is None]

    gravidade: Gravidade = "alta"
    texto = f" Já foram pedidos {total(a_caminho)}."
    if a_tempo:
        chega = sum(e.quantidade for e in a_tempo)
        dura = (max(insumo.estoque_atual, 0) + chega) / consumo
        ultima = max(e.previsto_para for e in a_tempo)
        texto += f" Chegam {total(a_tempo)} até {ultima:%d/%m/%Y}, antes de o estoque acabar"
        if dura > prazo:
            gravidade = "media"
            texto += f", e com eles ele dura cerca de {dias_legivel(dura)}: confira a entrega."
        else:
            texto += f", mas com eles ele dura só cerca de {dias_legivel(dura)}."
    if atrasados:
        previsto = min(e.previsto_para for e in atrasados)
        texto += (
            f" {total(atrasados)} estavam previstos para {previsto:%d/%m/%Y} e ainda não "
            "chegaram: cobre a revenda."
        )
    if tarde:
        texto += (
            f" {total(tarde)} só chegam em {min(e.previsto_para for e in tarde):%d/%m/%Y}, "
            "depois de o estoque acabar."
        )
    if sem_data:
        texto += f" {total(sem_data)} não têm data prevista de chegada."
    return gravidade, texto


def _reposicao(
    insumo: Insumo,
    consumo: float,
    prazo: int,
    referencia: date,
    custo_medio: float | None,
    em_pedido: float = 0.0,
) -> Reposicao:
    minimo = insumo.estoque_minimo or 0.0
    # O que já foi pedido conta como se estivesse no galpão: sem isso, a sugestão manda
    # comprar de novo o que está a caminho. Se ele chega a tempo é assunto do alerta de falta.
    posicao = max(insumo.estoque_atual, 0.0) + em_pedido
    # Pedir no dia em que o estoque acima do mínimo cobre exatamente o prazo de entrega.
    dias_ate_pedir = max(0, math.floor((posicao - minimo) / consumo - prazo))
    no_pedido = posicao - consumo * dias_ate_pedir
    # Se acabar antes da entrega, a falta não é recuperada: chega-se com zero, não negativo.
    na_chegada = max(0.0, no_pedido - consumo * prazo)
    # Para cima e inteiro: não se compra 29,32 sacas. O round tira o resíduo do float,
    # que faria um 60,0000001 virar 61.
    pela_conta = math.ceil(round(minimo + consumo * HORIZONTE_COMPRA_DIAS - na_chegada, 3))
    pedir_em = referencia + timedelta(days=dias_ate_pedir)

    unidade = insumo.unidade
    ajustes = []
    quantidade = pela_conta
    if insumo.pedido_minimo and insumo.pedido_minimo > quantidade:
        quantidade = insumo.pedido_minimo
        ajustes.append(f"subiu para o pedido mínimo de {quantidade_legivel(quantidade, unidade)}")
    o_que = quantidade_legivel(quantidade, unidade)
    if insumo.embalagem:
        # Para cima: embalagem aberta não se compra. O round tira o resíduo da divisão.
        embalagens = math.ceil(round(quantidade / insumo.embalagem, 6))
        fechadas = round(embalagens * insumo.embalagem, 3)
        if fechadas != quantidade:
            ajustes.append("foi arredondada para cima em embalagens fechadas")
        quantidade = fechadas
        plural = "embalagem" if embalagens == 1 else "embalagens"
        o_que = (
            f"{embalagens} {plural} de {quantidade_legivel(insumo.embalagem, unidade)} "
            f"({quantidade_legivel(quantidade, unidade)})"
        )

    quando = "hoje" if dias_ate_pedir == 0 else f"até {pedir_em:%d/%m/%Y}"
    margem = f", mantendo o mínimo de {quantidade_legivel(minimo, unidade)}" if minimo else ""
    justificativa = (
        f"Pedir {quando} {o_que}: com entrega em "
        f"{dias_legivel(prazo)}, cobre {HORIZONTE_COMPRA_DIAS} dias de consumo "
        f"a {quantidade_legivel(consumo, unidade)}/dia{margem}."
    )
    if ajustes:
        justificativa += (
            f" A conta dá {quantidade_legivel(pela_conta, unidade)}; a quantidade "
            f"{' e '.join(ajustes)}."
        )
    if em_pedido:
        justificativa += (
            f" Desconta os {quantidade_legivel(em_pedido, unidade)} já pedidos e ainda não "
            "recebidos."
        )
    custo = None
    if custo_medio is not None:
        custo = round(quantidade * custo_medio, 2)
        justificativa += (
            f" {valor_pelo_custo_medio(custo_medio, unidade)}, a compra fica em cerca de "
            f"{dinheiro_legivel(custo)}."
        )
    return Reposicao(
        pedir_em=pedir_em,
        quantidade=quantidade,
        pedir_hoje=dias_ate_pedir == 0,
        justificativa=justificativa,
        custo_estimado=custo,
    )
