"""Casos de uso de insumo. A rota chama isto; isto chama banco e domínio."""

import uuid
from decimal import Decimal

from sqlalchemy import case, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.erros import InsumoComMovimentacoes, InsumoDuplicado, InsumoNaoEncontrado
from app.domain.estoque import TipoMovimentacao
from app.models import Insumo, Movimentacao
from app.schemas.insumo import InsumoEntrada, InsumoSaida

# Mesma regra de `domain.estoque.efeito_no_saldo`, expressa em SQL para que o
# saldo de todos os insumos saia numa única consulta agregada.
_EFEITO = case(
    (Movimentacao.tipo == TipoMovimentacao.COMPRA, Movimentacao.quantidade),
    else_=-Movimentacao.quantidade,
)


def saldo_do_insumo(db: Session, insumo_id: uuid.UUID) -> Decimal:
    consulta = select(func.coalesce(func.sum(_EFEITO), 0)).where(
        Movimentacao.insumo_id == insumo_id
    )
    return Decimal(db.scalar(consulta) or 0)


def _saida(insumo: Insumo, saldo: Decimal) -> InsumoSaida:
    return InsumoSaida(
        id=insumo.id,
        nome=insumo.nome,
        categoria=insumo.categoria,
        unidade=insumo.unidade,
        estoque_minimo=insumo.estoque_minimo,
        saldo_atual=saldo,
        criado_em=insumo.criado_em,
    )


def listar(db: Session) -> list[InsumoSaida]:
    saldos = (
        select(Movimentacao.insumo_id, func.sum(_EFEITO).label("saldo"))
        .group_by(Movimentacao.insumo_id)
        .subquery()
    )
    consulta = (
        select(Insumo, func.coalesce(saldos.c.saldo, 0))
        .outerjoin(saldos, saldos.c.insumo_id == Insumo.id)
        .order_by(func.lower(Insumo.nome))
    )
    return [_saida(insumo, Decimal(saldo)) for insumo, saldo in db.execute(consulta)]


def _buscar(db: Session, insumo_id: uuid.UUID) -> Insumo:
    insumo = db.get(Insumo, insumo_id)
    if insumo is None:
        raise InsumoNaoEncontrado()
    return insumo


def obter(db: Session, insumo_id: uuid.UUID) -> InsumoSaida:
    return _saida(_buscar(db, insumo_id), saldo_do_insumo(db, insumo_id))


def _gravar(db: Session, insumo: Insumo) -> None:
    try:
        db.commit()
    except IntegrityError as erro:
        # A unicidade é garantida pelo índice `uq_insumo_nome_lower`, não por uma
        # consulta prévia: consultar e depois inserir tem janela de corrida.
        db.rollback()
        raise InsumoDuplicado(insumo.nome) from erro
    db.refresh(insumo)


def criar(db: Session, dados: InsumoEntrada) -> InsumoSaida:
    insumo = Insumo(**dados.model_dump())
    db.add(insumo)
    _gravar(db, insumo)
    return _saida(insumo, Decimal(0))


def atualizar(db: Session, insumo_id: uuid.UUID, dados: InsumoEntrada) -> InsumoSaida:
    insumo = _buscar(db, insumo_id)
    for campo, valor in dados.model_dump().items():
        setattr(insumo, campo, valor)
    _gravar(db, insumo)
    return _saida(insumo, saldo_do_insumo(db, insumo_id))


def remover(db: Session, insumo_id: uuid.UUID) -> None:
    insumo = _buscar(db, insumo_id)
    # Apagar o insumo apagaria o histórico de consumo junto — e o histórico é a
    # matéria-prima de toda análise. Recusado; o banco também recusa (RESTRICT).
    if db.scalar(select(exists().where(Movimentacao.insumo_id == insumo_id))):
        raise InsumoComMovimentacoes()
    db.delete(insumo)
    db.commit()
