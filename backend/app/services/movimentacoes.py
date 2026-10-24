"""Casos de uso de movimentação (compra e retirada)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import estoque
from app.domain.erros import InsumoNaoEncontrado, MovimentacaoNaoEncontrada
from app.models import Insumo, Movimentacao
from app.schemas.movimentacao import MovimentacaoEntrada, MovimentacaoSaida
from app.services.insumos import saldo_do_insumo


def _saida(mov: Movimentacao) -> MovimentacaoSaida:
    return MovimentacaoSaida(
        id=mov.id,
        insumo_id=mov.insumo_id,
        insumo_nome=mov.insumo.nome,
        insumo_unidade=mov.insumo.unidade,
        tipo=mov.tipo,
        quantidade=mov.quantidade,
        data=mov.data,
        validade=mov.validade,
        observacao=mov.observacao,
        criado_em=mov.criado_em,
    )


def listar(db: Session, insumo_id: uuid.UUID | None = None) -> list[MovimentacaoSaida]:
    consulta = select(Movimentacao).order_by(
        Movimentacao.data.desc(), Movimentacao.criado_em.desc()
    )
    if insumo_id is not None:
        consulta = consulta.where(Movimentacao.insumo_id == insumo_id)
    return [_saida(mov) for mov in db.scalars(consulta)]


def registrar(db: Session, dados: MovimentacaoEntrada) -> MovimentacaoSaida:
    insumo = db.get(Insumo, dados.insumo_id)
    if insumo is None:
        raise InsumoNaoEncontrado()
    estoque.validar_inclusao(
        saldo_do_insumo(db, insumo.id), dados.tipo, dados.quantidade, insumo.unidade
    )
    mov = Movimentacao(**dados.model_dump())
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return _saida(mov)


def remover(db: Session, movimentacao_id: uuid.UUID) -> None:
    mov = db.get(Movimentacao, movimentacao_id)
    if mov is None:
        raise MovimentacaoNaoEncontrada()
    estoque.validar_remocao(
        saldo_do_insumo(db, mov.insumo_id), mov.tipo, mov.quantidade, mov.insumo.unidade
    )
    db.delete(mov)
    db.commit()
