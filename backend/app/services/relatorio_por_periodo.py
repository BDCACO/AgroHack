"""O relatório por período (GET /relatorios/periodo): lê do banco o que as somas do domínio
(`app/domain/relatorio_por_periodo.py`) precisam, em três consultas, qualquer que seja o
tamanho do período ou o número de insumos: as movimentações do período, os insumos delas
(com a categoria) e as compras com preço desses insumos, para o custo médio de hoje."""

from dataclasses import replace
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, lazyload

from app.domain import estoque as regras
from app.domain import relatorio_por_periodo as dominio
from app.models import Insumo, Movimentacao
from app.services.estoque import FiltroDeMovimentacoes, condicoes_do_filtro

# Sem datas, o ano que o produtor compara: doze meses com o atual, sem escolher nada.
MESES_NO_PADRAO = 12
# O que o recorte deixa de fora, para quem lê as somas não achar que faltou registro.
_SO_APLICACOES = (
    "Com o filtro de talhão, só as aplicações nele entram: compra e perda não são de "
    "talhão, e o gasto e as perdas ficam zerados."
)
_SO_COMPRAS = (
    "Com o filtro de fornecedor, só as compras dele entram: consumo e perda não são de "
    "fornecedor, e ficam zerados."
)


def gerar(
    db: Session,
    desde: date,
    ate: date,
    agrupar: dominio.Agrupamento,
    *,
    categoria_id: int | None = None,
    insumo_id: int | None = None,
    talhao_id: int | None = None,
    fornecedor_id: int | None = None,
) -> dominio.RelatorioPorPeriodo:
    # Antes de consultar: o pedido de séculos por dia é recusado sem ler o banco.
    dominio.periodos(desde, ate, agrupar)
    filtro = FiltroDeMovimentacoes(
        insumo_id=insumo_id,
        categoria_id=categoria_id,
        talhao_id=talhao_id,
        fornecedor_id=fornecedor_id,
        desde=desde,
        ate=ate,
    )
    movimentacoes = db.scalars(
        select(Movimentacao)
        .where(*condicoes_do_filtro(db, filtro))
        # O fornecedor vem junto (o nome); quem lançou não é lido aqui, e não precisa vir.
        .options(lazyload(Movimentacao.usuario))
    ).all()
    ids = {m.insumo_id for m in movimentacoes}
    insumos = {insumo.id: insumo for insumo in db.scalars(select(Insumo).where(Insumo.id.in_(ids)))}
    custos = _custos_medios(db, ids)
    resultado = dominio.relatorio(
        (
            dominio.Lancamento(
                m.data,
                m.insumo_id,
                m.tipo,
                m.motivo,
                m.quantidade,
                m.valor_unitario,
                m.fornecedor_id,
                m.comprado_de,
            )
            for m in movimentacoes
        ),
        {
            insumo.id: dominio.InsumoDoRelatorio(
                insumo.id,
                insumo.nome,
                insumo.unidade,
                insumo.categoria_id,
                None if insumo.categoria is None else insumo.categoria.nome,
                custos.get(insumo.id),
            )
            for insumo in insumos.values()
        },
        desde,
        ate,
        agrupar,
    )
    recortes = [
        frase
        for frase, ligado in ((_SO_APLICACOES, talhao_id), (_SO_COMPRAS, fornecedor_id))
        if ligado is not None
    ]
    return replace(resultado, limitacoes=[*recortes, *resultado.limitacoes])


def inicio_dos_ultimos_meses(ate: date, meses: int = MESES_NO_PADRAO) -> date:
    """O primeiro dia do mês, `meses - 1` meses antes de `ate`: com o mês de `ate`, são
    `meses` meses."""
    contagem = ate.year * 12 + ate.month - 1 - (meses - 1)
    return date(contagem // 12, contagem % 12 + 1, 1)


def _custos_medios(db: Session, insumo_ids: set[int]) -> dict[int, float | None]:
    """O custo médio de hoje de cada insumo, pela regra da tela do insumo e do /resumo:
    todas as compras com preço, de qualquer data, e não só as do período."""
    compras: dict[int, list[regras.Entrada]] = {}
    consulta = select(
        Movimentacao.insumo_id,
        Movimentacao.data,
        Movimentacao.quantidade,
        Movimentacao.valor_unitario,
    ).where(
        Movimentacao.insumo_id.in_(insumo_ids),
        Movimentacao.tipo == "entrada",
        Movimentacao.valor_unitario.is_not(None),
    )
    for insumo_id, data, quantidade, valor_unitario in db.execute(consulta):
        compras.setdefault(insumo_id, []).append(
            regras.Entrada(data, quantidade, valor_unitario=valor_unitario)
        )
    return {insumo_id: regras.custo_medio(entradas) for insumo_id, entradas in compras.items()}
