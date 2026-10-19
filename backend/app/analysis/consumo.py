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
    Insumo,
    Lote,
    Retirada,
    alerta_estoque_minimo,
    alertas_de_validade,
    dias_legivel,
    quantidade_legivel,
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
    quantidade: int
    justificativa: str


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
) -> Analise:
    """Analisa o insumo na data de referência.

    `registros_desde` é a data a partir da qual as retiradas estão completas: é o que
    separa "não houve consumo" de "não havia registro".
    """
    alertas = alertas_de_validade(lotes, referencia, insumo.unidade)
    if (alerta := alerta_estoque_minimo(insumo)) is not None:
        alertas.append(alerta)
    limitacoes = []
    if insumo.estoque_minimo is None:
        limitacoes.append(
            "Estoque mínimo não cadastrado: sem alerta de mínimo, e a reposição não "
            "guarda margem de segurança."
        )
    if insumo.estoque_atual < 0:
        limitacoes.append("Estoque atual negativo: há entrada ou saída faltando nos registros.")

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
        alertas.append(
            Alerta(
                "risco_de_falta",
                "alta",
                f"No ritmo atual ({ritmo}), o estoque dura cerca de {dias_legivel(cobertura)}"
                f" — menos que o prazo de reposição de {dias_legivel(prazo)}.",
            )
        )
    elif cobertura > COBERTURA_EXCESSO_DIAS:
        alertas.append(
            Alerta(
                "excesso",
                "baixa",
                f"No ritmo atual ({ritmo}), o estoque dura cerca de {dias_legivel(cobertura)}"
                f" — mais de {COBERTURA_EXCESSO_DIAS} dias de capital parado.",
            )
        )
        # Com excesso não há compra a sugerir — e isso limita a data do pedido a
        # COBERTURA_EXCESSO_DIAS, em vez de séculos à frente com consumo ínfimo.
        return resultado(consumo=consumo, cobertura=cobertura)

    limitacoes.append(
        "A quantidade sugerida não considera embalagem, pedido mínimo do fornecedor nem preço."
    )
    reposicao = _reposicao(insumo, consumo, prazo, referencia)
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


def _reposicao(insumo: Insumo, consumo: float, prazo: int, referencia: date) -> Reposicao:
    minimo = insumo.estoque_minimo or 0.0
    estoque = max(insumo.estoque_atual, 0.0)
    # Pedir no dia em que o estoque acima do mínimo cobre exatamente o prazo de entrega.
    dias_ate_pedir = max(0, math.floor((estoque - minimo) / consumo - prazo))
    no_pedido = estoque - consumo * dias_ate_pedir
    # Se acabar antes da entrega, a falta não é recuperada: chega-se com zero, não negativo.
    na_chegada = max(0.0, no_pedido - consumo * prazo)
    # Para cima e inteiro: não se compra 29,32 sacas. O round tira o resíduo do float,
    # que faria um 60,0000001 virar 61.
    quantidade = math.ceil(round(minimo + consumo * HORIZONTE_COMPRA_DIAS - na_chegada, 3))
    pedir_em = referencia + timedelta(days=dias_ate_pedir)

    unidade = insumo.unidade
    quando = "hoje" if dias_ate_pedir == 0 else f"até {pedir_em:%d/%m/%Y}"
    margem = f", mantendo o mínimo de {quantidade_legivel(minimo, unidade)}" if minimo else ""
    return Reposicao(
        pedir_em=pedir_em,
        quantidade=quantidade,
        justificativa=(
            f"Pedir {quando} {quantidade_legivel(quantidade, unidade)}: com entrega em "
            f"{dias_legivel(prazo)}, cobre {HORIZONTE_COMPRA_DIAS} dias de consumo "
            f"a {quantidade_legivel(consumo, unidade)}/dia{margem}."
        ),
    )
