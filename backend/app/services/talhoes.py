"""Casos de uso dos talhões: o cadastro, e a carência e o custo do que foi aplicado em
cada um."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Talhao
from app.schemas.talhao import TalhaoCadastro, TalhaoResposta


class NomeDuplicado(Exception):
    pass


class TalhaoInexistente(Exception):
    pass


def listar_talhoes(db: Session) -> list[TalhaoResposta]:
    return [_resposta(t) for t in db.scalars(select(Talhao).order_by(Talhao.nome))]


def criar_talhao(db: Session, dados: TalhaoCadastro) -> TalhaoResposta:
    talhao = Talhao(**dados.model_dump())
    db.add(talhao)
    _salvar(db)
    return _resposta(talhao)


def atualizar_talhao(db: Session, talhao_id: int, dados: TalhaoCadastro) -> TalhaoResposta:
    talhao = buscar_talhao(db, talhao_id)
    for campo, valor in dados.model_dump().items():
        setattr(talhao, campo, valor)
    _salvar(db)
    return _resposta(talhao)


def detalhar_talhao(db: Session, talhao_id: int) -> TalhaoResposta:
    return _resposta(buscar_talhao(db, talhao_id))


def remover_talhao(db: Session, talhao_id: int) -> None:
    db.delete(buscar_talhao(db, talhao_id))
    db.commit()


def buscar_talhao(db: Session, talhao_id: int) -> Talhao:
    talhao = db.get(Talhao, talhao_id)
    if talhao is None:
        raise TalhaoInexistente
    return talhao


def _salvar(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        # A única restrição que a validação do schema não cobre é o nome único.
        raise NomeDuplicado from erro


def _resposta(talhao: Talhao) -> TalhaoResposta:
    return TalhaoResposta.model_validate(talhao)
