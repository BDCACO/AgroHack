"""Casos de uso do estoque: cadastro de insumos, movimentações e a análise de cada
insumo a partir do que está no banco."""

from dataclasses import replace
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.analysis.consumo import analisar
from app.core.relogio import hoje
from app.domain import estoque as dominio
from app.models import Insumo, Movimentacao
from app.schemas.estoque import (
    AjusteDeInventario,
    ContagemDeInventario,
    InsumoCadastro,
    InsumoDetalhe,
    InsumoResposta,
    MovimentacaoEntrada,
    MovimentacaoResposta,
    PontoDeEstoque,
)


class NomeDuplicado(Exception):
    pass


class InsumoInexistente(Exception):
    pass


def listar_insumos(db: Session) -> list[InsumoResposta]:
    insumos = db.scalars(
        select(Insumo).options(selectinload(Insumo.movimentacoes)).order_by(Insumo.nome)
    )
    referencia = hoje()
    return [_resposta(insumo, referencia) for insumo in insumos]


def criar_insumo(db: Session, dados: InsumoCadastro) -> InsumoResposta:
    insumo = Insumo(**dados.model_dump())
    db.add(insumo)
    _salvar(db)
    return _resposta(insumo, hoje())


def atualizar_insumo(db: Session, insumo_id: int, dados: InsumoCadastro) -> InsumoResposta:
    insumo = _buscar_insumo(db, insumo_id)
    for campo, valor in dados.model_dump().items():
        setattr(insumo, campo, valor)
    _salvar(db)
    return _resposta(insumo, hoje())


def detalhar_insumo(db: Session, insumo_id: int) -> InsumoDetalhe:
    insumo = _buscar_insumo(db, insumo_id)
    movimentacoes = sorted(insumo.movimentacoes, key=lambda m: (m.data, m.id))
    saldo, por_dia = 0.0, {}
    for m in movimentacoes:
        saldo += m.quantidade if m.tipo == "entrada" else -m.quantidade
        # Vários lançamentos no mesmo dia: vale o saldo depois do último.
        por_dia[m.data] = round(saldo, 3)
    return InsumoDetalhe(
        **dict(_resposta(insumo, hoje())),
        historico=[PontoDeEstoque(data=dia, saldo=valor) for dia, valor in por_dia.items()],
        movimentacoes=[MovimentacaoResposta.model_validate(m) for m in reversed(movimentacoes)],
    )


def remover_insumo(db: Session, insumo_id: int) -> None:
    # As movimentações vão junto pelo ON DELETE CASCADE.
    db.delete(_buscar_insumo(db, insumo_id))
    db.commit()


def listar_movimentacoes(db: Session, insumo_id: int | None, limite: int) -> list[Movimentacao]:
    consulta = select(Movimentacao).order_by(Movimentacao.data.desc(), Movimentacao.id.desc())
    if insumo_id is not None:
        consulta = consulta.where(Movimentacao.insumo_id == insumo_id)
    return list(db.scalars(consulta.limit(limite)))


def registrar_movimentacao(db: Session, dados: MovimentacaoEntrada) -> Movimentacao:
    _buscar_insumo(db, dados.insumo_id)
    movimentacao = Movimentacao(**dados.model_dump())
    db.add(movimentacao)
    db.commit()
    return movimentacao


def registrar_inventario(
    db: Session, insumo_id: int, contagem: ContagemDeInventario
) -> AjusteDeInventario:
    """Compara a contagem do galpão com o saldo registrado até aquele dia e lança a
    diferença: o estoque passa a ser o que foi contado."""
    insumo = _buscar_insumo(db, insumo_id)
    saldo = round(
        sum(
            m.quantidade if m.tipo == "entrada" else -m.quantidade
            for m in insumo.movimentacoes
            if m.data <= contagem.data
        ),
        3,
    )
    diferenca = round(contagem.quantidade_contada - saldo, 3)
    movimentacao = None
    if diferenca:
        movimentacao = Movimentacao(
            insumo_id=insumo.id,
            tipo="entrada" if diferenca > 0 else "saida",
            motivo="inventario",
            data=contagem.data,
            quantidade=abs(diferenca),
        )
        db.add(movimentacao)
        db.commit()
    return AjusteDeInventario(
        saldo_registrado=saldo,
        quantidade_contada=contagem.quantidade_contada,
        diferenca=diferenca,
        movimentacao=movimentacao and MovimentacaoResposta.model_validate(movimentacao),
    )


def remover_movimentacao(db: Session, movimentacao_id: int) -> bool:
    movimentacao = db.get(Movimentacao, movimentacao_id)
    if movimentacao is None:
        return False
    db.delete(movimentacao)
    db.commit()
    return True


def _buscar_insumo(db: Session, insumo_id: int) -> Insumo:
    insumo = db.get(Insumo, insumo_id)
    if insumo is None:
        raise InsumoInexistente
    return insumo


def _salvar(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        # A única restrição que a validação do schema não cobre é o nome único.
        raise NomeDuplicado from erro


def _resposta(insumo: Insumo, referencia: date) -> InsumoResposta:
    entradas = [
        dominio.Entrada(m.data, m.quantidade, m.validade)
        for m in insumo.movimentacoes
        if m.tipo == "entrada"
    ]
    saidas = [m for m in insumo.movimentacoes if m.tipo == "saida"]
    # Só a retirada para uso é consumo; descarte e ajuste de inventário tiram do estoque,
    # mas não do ritmo.
    retiradas = [dominio.Retirada(m.data, m.quantidade) for m in saidas if m.motivo is None]
    descartes = [dominio.Descarte(m.data, m.quantidade) for m in saidas if m.motivo == "descarte"]
    # Produto que faltou na contagem saiu sem registro, como uma retirada: dos lotes bons.
    faltas = [dominio.Retirada(m.data, m.quantidade) for m in saidas if m.motivo == "inventario"]
    # Quantidades têm no máximo 3 casas; arredondar a soma tira o resíduo do float
    # (sem isso, um estoque zerado poderia virar 1e-14 e escapar do alerta).
    estoque = round(sum(e.quantidade for e in entradas) - sum(m.quantidade for m in saidas), 3)
    # Sem movimentação nenhuma, o histórico começa hoje: a análise diz que é curto.
    registros_desde = min((m.data for m in insumo.movimentacoes), default=referencia)

    analise = analisar(
        dominio.Insumo(
            insumo.nome,
            insumo.unidade,
            estoque,
            insumo.estoque_minimo,
            insumo.prazo_reposicao_dias,
        ),
        retiradas,
        lotes=dominio.lotes_em_estoque(entradas, retiradas + faltas, descartes),
        registros_desde=min(registros_desde, referencia),
        referencia=referencia,
    )
    if any(e.validade for e in entradas):
        limitacao = (
            "Saldo por lote estimado: as retiradas não dizem de qual lote saíram, então "
            "se supõe que o que vence primeiro é usado primeiro."
        )
        analise = replace(analise, limitacoes=[*analise.limitacoes, limitacao])
    if any(m.motivo == "inventario" for m in insumo.movimentacoes):
        limitacao = (
            "Houve ajuste de inventário: a diferença da contagem corrige o estoque, mas não "
            "entra no ritmo de consumo, porque não se sabe quando o produto saiu."
        )
        analise = replace(analise, limitacoes=[*analise.limitacoes, limitacao])
    return InsumoResposta(
        id=insumo.id,
        demonstracao=insumo.demonstracao,
        nome=insumo.nome,
        unidade=insumo.unidade,
        estoque_minimo=insumo.estoque_minimo,
        prazo_reposicao_dias=insumo.prazo_reposicao_dias,
        estoque_atual=estoque,
        analise=analise,
    )
