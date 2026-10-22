"""Casos de uso dos talhões: o cadastro, e a carência e o custo do que foi aplicado em
cada um."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Movimentacao, Talhao
from app.schemas.talhao import TalhaoCadastro, TalhaoResposta


class NomeDuplicado(Exception):
    pass


class TalhaoInexistente(Exception):
    pass


class TalhaoComAplicacoes(Exception):
    """Remover o talhão apagaria (ou deixaria sem dono) o registro de onde cada insumo foi
    aplicado: a rastreabilidade que a carência e o custo usam."""

    def __init__(self, nome: str, aplicacoes: int) -> None:
        quantas = (
            "1 aplicação registrada" if aplicacoes == 1 else f"{aplicacoes} aplicações registradas"
        )
        super().__init__(
            f"{nome} tem {quantas}: removê-lo apagaria para onde foi cada insumo. Remova as "
            "aplicações antes, se foram lançadas por engano."
        )


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
    talhao = buscar_talhao(db, talhao_id)
    aplicacoes = db.scalar(
        select(func.count()).select_from(Movimentacao).where(Movimentacao.talhao_id == talhao_id)
    )
    if aplicacoes:
        raise TalhaoComAplicacoes(talhao.nome, aplicacoes)
    db.delete(talhao)
    try:
        db.commit()
    except IntegrityError as erro:
        # Uma aplicação lançada entre a contagem e o DELETE: o RESTRICT do banco barra.
        db.rollback()
        raise TalhaoComAplicacoes(talhao.nome, 1) from erro


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
