"""A visão geral do estoque em reais: quanto vale o que está no galpão, quanto se perdeu
e quanto custam as compras que vêm por aí.

Soma o que a análise de cada insumo já calculou (`estoque.listar_insumos`), em vez de
refazer a conta: o resumo não pode discordar da tela de cada insumo.
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.relogio import hoje
from app.models import Movimentacao
from app.schemas.estoque import (
    AlertasPorGravidade,
    ComprasSugeridas,
    InsumoResposta,
    Perdas,
    Resumo,
)
from app.services import estoque, talhoes

# Até onde olhar as compras sugeridas e as perdas recentes: um mês, o horizonte de quem
# planeja o caixa.
JANELA_DIAS = 30


def gerar(db: Session) -> Resumo:
    return resumir(db, estoque.listar_insumos(db), hoje())


def resumir(db: Session, insumos: list[InsumoResposta], referencia: date) -> Resumo:
    """Para quem já tem a lista analisada (o relatório), sem analisar tudo de novo."""
    custos = {i.id: i.custo_medio for i in insumos}
    sem_preco = sum(custo is None for custo in custos.values())
    com_valor = [i.valor_em_estoque for i in insumos if i.valor_em_estoque is not None]

    # Perda é o que saiu sem ser usado: descarte e falta na contagem. Sobra não desconta.
    perdas = db.scalars(
        select(Movimentacao).where(
            Movimentacao.tipo == "saida", Movimentacao.motivo.in_(("descarte", "inventario"))
        )
    )
    inicio = referencia - timedelta(days=JANELA_DIAS - 1)
    total = recentes = 0.0
    for perda in perdas:
        if (custo := custos.get(perda.insumo_id)) is None:
            continue
        valor = perda.quantidade * custo
        total += valor
        if perda.data >= inicio:
            recentes += valor

    limite = referencia + timedelta(days=JANELA_DIAS)
    reposicoes = [
        i.analise.reposicao
        for i in insumos
        if i.analise.reposicao and i.analise.reposicao.pedir_em <= limite
    ]
    custos_estimados = [r.custo_estimado for r in reposicoes if r.custo_estimado is not None]

    # Só os alertas dos insumos: o Painel mostra esses números ao lado da lista de alertas
    # dos insumos, e um urgente a mais sem cartão confundiria. A carência é do talhão, e vem
    # contada à parte.
    contagem = dict.fromkeys(("alta", "media", "baixa"), 0)
    for insumo in insumos:
        for alerta in insumo.analise.alertas:
            contagem[alerta.gravidade] += 1

    limitacoes = []
    if sem_preco:
        sujeito = "1 insumo" if sem_preco == 1 else f"{sem_preco} insumos"
        verbo = "fica" if sem_preco == 1 else "ficam"
        limitacoes.append(
            f"{sujeito} sem preço nas compras {verbo} fora do valor em estoque, das perdas e "
            "do custo das compras."
        )
    if total:
        limitacoes.append("Perdas valorizadas pelo custo médio de hoje, não pelo preço da época.")

    return Resumo(
        insumos=len(insumos),
        valor_em_estoque=round(sum(com_valor), 2) if com_valor else None,
        insumos_sem_preco=sem_preco,
        perdas=Perdas(ultimos_30_dias=round(recentes, 2), total=round(total, 2)),
        compras_sugeridas=ComprasSugeridas(
            valor=round(sum(custos_estimados), 2) if custos_estimados else None,
            pedidos=len(reposicoes),
            pedir_hoje=sum(r.pedir_hoje for r in reposicoes),
        ),
        alertas=AlertasPorGravidade(**contagem),
        talhoes_em_carencia=talhoes.em_carencia(db, referencia),
        limitacoes=limitacoes,
    )
