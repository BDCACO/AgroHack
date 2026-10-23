"""Casos de uso dos fornecedores: o cadastro das revendas e o que se pagou a cada uma."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import violou_nome_unico
from app.models import Fornecedor, Insumo, Movimentacao, Pedido
from app.schemas.compras import FornecedorCadastro, FornecedorDetalhe, FornecedorResposta
from app.schemas.estoque import MovimentacaoResposta
from app.services.estoque import precos_pagos

# Compras no detalhe do fornecedor: as recentes bastam para conferir; o preço por insumo
# resume todas.
COMPRAS_RECENTES = 20


class NomeDuplicado(Exception):
    pass


class FornecedorInexistente(Exception):
    pass


class FornecedorComHistoria(Exception):
    """Remover o fornecedor apagaria de quem foi cada compra e o preço pago a ele: a
    comparação entre revendas some. Desativar o tira das escolhas e guarda a história."""

    def __init__(self, nome: str, compras: int, pedidos: int) -> None:
        partes = [
            f"{quantas} {palavra if quantas == 1 else plural}"
            for quantas, palavra, plural in (
                (compras, "compra", "compras"),
                (pedidos, "pedido", "pedidos"),
            )
            if quantas
        ]
        super().__init__(
            f"{nome} tem {' e '.join(partes)} no histórico: removê-lo apagaria de quem foi cada "
            "compra e o preço pago a ele. Desative-o (ativo: false): ele sai das escolhas, e a "
            "história fica."
        )


def listar_fornecedores(db: Session) -> list[Fornecedor]:
    return list(db.scalars(select(Fornecedor).order_by(Fornecedor.nome)))


def criar_fornecedor(db: Session, dados: FornecedorCadastro) -> Fornecedor:
    fornecedor = Fornecedor(**dados.model_dump())
    db.add(fornecedor)
    _salvar(db)
    return fornecedor


def atualizar_fornecedor(db: Session, fornecedor_id: int, dados: FornecedorCadastro) -> Fornecedor:
    """Muda só o que veio: a tela que só desativa não apaga o telefone."""
    fornecedor = buscar_fornecedor(db, fornecedor_id)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(fornecedor, campo, valor)
    _salvar(db)
    return fornecedor


def detalhar_fornecedor(db: Session, fornecedor_id: int) -> FornecedorDetalhe:
    """O fornecedor, as compras recentes e o preço médio pago a ele por cada insumo."""
    fornecedor = buscar_fornecedor(db, fornecedor_id)
    compras = db.execute(
        select(Movimentacao, Insumo)
        .join(Insumo)
        .where(Movimentacao.fornecedor_id == fornecedor_id)
        .order_by(Movimentacao.data.desc(), Movimentacao.id.desc())
    ).all()
    return FornecedorDetalhe(
        **FornecedorResposta.model_validate(fornecedor).model_dump(),
        compras=[MovimentacaoResposta.model_validate(m) for m, _ in compras[:COMPRAS_RECENTES]],
        precos=sorted(precos_pagos([(m, insumo) for m, insumo in compras]), key=lambda p: p.insumo),
    )


def remover_fornecedor(db: Session, fornecedor_id: int) -> None:
    fornecedor = buscar_fornecedor(db, fornecedor_id)
    compras = db.scalar(
        select(func.count())
        .select_from(Movimentacao)
        .where(Movimentacao.fornecedor_id == fornecedor_id)
    )
    pedidos = db.scalar(
        select(func.count()).select_from(Pedido).where(Pedido.fornecedor_id == fornecedor_id)
    )
    if compras or pedidos:
        raise FornecedorComHistoria(fornecedor.nome, compras, pedidos)
    db.delete(fornecedor)
    try:
        db.commit()
    except IntegrityError as erro:
        # Uma compra lançada entre a contagem e o DELETE: o RESTRICT do banco barra.
        db.rollback()
        raise FornecedorComHistoria(fornecedor.nome, 1, 0) from erro


def buscar_fornecedor(db: Session, fornecedor_id: int) -> Fornecedor:
    fornecedor = db.get(Fornecedor, fornecedor_id)
    if fornecedor is None:
        raise FornecedorInexistente
    return fornecedor


def _salvar(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        # Só o nome único vira "já existe", como no insumo e no talhão.
        if violou_nome_unico(erro, "fornecedores"):
            raise NomeDuplicado from erro
        raise
