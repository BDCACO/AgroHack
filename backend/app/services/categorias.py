"""Casos de uso das categorias de insumo: o cadastro, e quantos insumos cada uma tem."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import violou_nome_unico
from app.models import Categoria, Insumo
from app.schemas.categoria import CategoriaCadastro, CategoriaResposta


class NomeDuplicado(Exception):
    pass


class CategoriaInexistente(Exception):
    pass


class CategoriaComInsumos(Exception):
    """Remover a categoria deixaria os insumos dela sem categoria, calados: o filtro e os
    totais por categoria mudariam sem ninguém pedir. A tela pede para mudá-los antes."""

    def __init__(self, nome: str, insumos: int) -> None:
        quantos = "1 insumo" if insumos == 1 else f"{insumos} insumos"
        super().__init__(
            f"{nome} tem {quantos}: mude-os de categoria na tela de Insumos antes de removê-la."
        )


def listar_categorias(db: Session) -> list[CategoriaResposta]:
    # Uma consulta só, com a contagem junto: sem uma ida ao banco por categoria.
    consulta = (
        select(Categoria, func.count(Insumo.id))
        .outerjoin(Insumo, Insumo.categoria_id == Categoria.id)
        .group_by(Categoria.id)
        .order_by(Categoria.nome)
    )
    return [_resposta(categoria, insumos) for categoria, insumos in db.execute(consulta)]


def criar_categoria(db: Session, dados: CategoriaCadastro) -> CategoriaResposta:
    categoria = Categoria(nome=dados.nome)
    db.add(categoria)
    _salvar(db)
    return _resposta(categoria, 0)


def atualizar_categoria(
    db: Session, categoria_id: int, dados: CategoriaCadastro
) -> CategoriaResposta:
    categoria = _buscar(db, categoria_id)
    categoria.nome = dados.nome
    _salvar(db)
    return _resposta(categoria, _insumos_na(db, categoria_id))


def remover_categoria(db: Session, categoria_id: int) -> None:
    categoria = _buscar(db, categoria_id)
    if insumos := _insumos_na(db, categoria_id):
        raise CategoriaComInsumos(categoria.nome, insumos)
    db.delete(categoria)
    try:
        db.commit()
    except IntegrityError as erro:
        # Um insumo posto nela entre a contagem e o DELETE: o RESTRICT do banco barra.
        db.rollback()
        raise CategoriaComInsumos(categoria.nome, 1) from erro


def _insumos_na(db: Session, categoria_id: int) -> int:
    return db.scalar(
        select(func.count()).select_from(Insumo).where(Insumo.categoria_id == categoria_id)
    )


def _buscar(db: Session, categoria_id: int) -> Categoria:
    categoria = db.get(Categoria, categoria_id)
    if categoria is None:
        raise CategoriaInexistente
    return categoria


def _resposta(categoria: Categoria, insumos: int) -> CategoriaResposta:
    return CategoriaResposta(id=categoria.id, nome=categoria.nome, insumos=insumos)


def _salvar(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        # Só o nome único vira "já existe", como no insumo e no fornecedor.
        if violou_nome_unico(erro, "categorias"):
            raise NomeDuplicado from erro
        raise
