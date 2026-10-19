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
from app.schemas.estoque import InsumoCadastro, InsumoResposta, MovimentacaoEntrada


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
    retiradas = [
        dominio.Retirada(m.data, m.quantidade) for m in insumo.movimentacoes if m.tipo == "saida"
    ]
    # Quantidades têm no máximo 3 casas; arredondar a soma tira o resíduo do float
    # (sem isso, um estoque zerado poderia virar 1e-14 e escapar do alerta).
    estoque = round(sum(e.quantidade for e in entradas) - sum(r.quantidade for r in retiradas), 3)
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
        lotes=dominio.lotes_em_estoque(entradas, retiradas),
        registros_desde=min(registros_desde, referencia),
        referencia=referencia,
    )
    if any(e.validade for e in entradas):
        limitacao = (
            "Saldo por lote estimado: as retiradas não dizem de qual lote saíram, então "
            "se supõe que o que vence primeiro é usado primeiro."
        )
        analise = replace(analise, limitacoes=[*analise.limitacoes, limitacao])
    return InsumoResposta(
        id=insumo.id,
        nome=insumo.nome,
        unidade=insumo.unidade,
        estoque_minimo=insumo.estoque_minimo,
        prazo_reposicao_dias=insumo.prazo_reposicao_dias,
        estoque_atual=estoque,
        analise=analise,
    )
