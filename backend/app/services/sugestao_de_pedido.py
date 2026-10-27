"""O pedido sugerido: as reposições que o motor de análise manda fazer (hoje ou nos
próximos dias), agrupadas pelo fornecedor da última compra de cada insumo, com a
quantidade e o preço, para o produtor conferir e confirmar em POST /pedidos.

A quantidade é a da reposição: já em embalagens fechadas, com o pedido mínimo e
descontado o que está a caminho. Por isso o que já foi pedido não volta a ser sugerido.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.relogio import hoje
from app.models import Movimentacao
from app.schemas.compras import GrupoSugerido, ItemSugerido, SugestaoDePedido
from app.services import estoque


def sugerir(db: Session, dias: int) -> SugestaoDePedido:
    referencia = hoje()
    limite = referencia + timedelta(days=dias)
    a_pedir = [
        insumo
        for insumo in estoque.listar_insumos(db)
        if insumo.analise.reposicao is not None and insumo.analise.reposicao.pedir_em <= limite
    ]
    ultimas = _ultima_compra_com_fornecedor(db)
    grupos: dict[int | None, GrupoSugerido] = {}
    for insumo in a_pedir:
        reposicao = insumo.analise.reposicao
        ultima = ultimas.get(insumo.id)
        # Desativado não recebe pedido (POST /pedidos recusa): o insumo fica sem fornecedor.
        de_quem = ultima.fornecedor if ultima is not None and ultima.fornecedor.ativo else None
        preco = insumo.custo_medio
        if ultima is not None and ultima.valor_unitario is not None:
            # O preço da última compra, e não a média: é o que a revenda cobra hoje.
            preco = ultima.valor_unitario
        grupo = grupos.setdefault(
            None if de_quem is None else de_quem.id,
            GrupoSugerido(
                fornecedor_id=None if de_quem is None else de_quem.id,
                fornecedor=None if de_quem is None else de_quem.nome,
                itens=[],
                custo_estimado=None,
            ),
        )
        grupo.itens.append(
            ItemSugerido(
                insumo_id=insumo.id,
                insumo=insumo.nome,
                unidade=insumo.unidade,
                quantidade=reposicao.quantidade,
                valor_unitario=preco,
                custo_estimado=None if preco is None else round(reposicao.quantidade * preco, 2),
                pedir_em=reposicao.pedir_em,
                pedir_hoje=reposicao.pedir_hoje,
                justificativa=reposicao.justificativa,
            )
        )
    for grupo in grupos.values():
        # O que é para hoje primeiro.
        grupo.itens.sort(key=lambda i: (i.pedir_em, i.insumo))
        custos = [i.custo_estimado for i in grupo.itens if i.custo_estimado is not None]
        grupo.custo_estimado = round(sum(custos), 2) if custos else None

    limitacoes = []
    if grupos:
        limitacoes.append(
            "O fornecedor de cada insumo é o da última compra com fornecedor, e o preço é o "
            "dessa compra (sem ele, o custo médio): confirme com a revenda antes de fechar."
        )
    sem_preco = [i.insumo for g in grupos.values() for i in g.itens if i.valor_unitario is None]
    if sem_preco:
        limitacoes.append(
            f"Sem preço nas compras ({', '.join(sorted(sem_preco))}): o custo estimado não os "
            "inclui."
        )
    return SugestaoDePedido(
        referencia=referencia,
        dias=dias,
        # Por fornecedor, pelo nome; o grupo sem fornecedor por último.
        grupos=sorted(grupos.values(), key=lambda g: (g.fornecedor is None, g.fornecedor or "")),
        limitacoes=limitacoes,
    )


def _ultima_compra_com_fornecedor(db: Session) -> dict[int, Movimentacao]:
    compras = db.scalars(
        select(Movimentacao)
        .where(
            Movimentacao.tipo == "entrada",
            Movimentacao.motivo.is_(None),
            Movimentacao.fornecedor_id.is_not(None),
        )
        .order_by(Movimentacao.data, Movimentacao.id)
    )
    # Na ordem do tempo: a última de cada insumo fica.
    return {m.insumo_id: m for m in compras}
