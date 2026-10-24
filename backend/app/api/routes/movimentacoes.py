import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.erros import RESPOSTAS_DE_ERRO
from app.core.database import get_db
from app.schemas.movimentacao import MovimentacaoEntrada, MovimentacaoSaida
from app.services import movimentacoes

router = APIRouter(prefix="/movimentacoes", tags=["movimentacoes"], responses=RESPOSTAS_DE_ERRO)


@router.get("", response_model=list[MovimentacaoSaida])
def listar(
    insumo_id: uuid.UUID | None = None, db: Session = Depends(get_db)
) -> list[MovimentacaoSaida]:
    """Mais recentes primeiro. `insumo_id` filtra por um insumo."""
    return movimentacoes.listar(db, insumo_id)


@router.post("", response_model=MovimentacaoSaida, status_code=status.HTTP_201_CREATED)
def registrar(dados: MovimentacaoEntrada, db: Session = Depends(get_db)) -> MovimentacaoSaida:
    return movimentacoes.registrar(db, dados)


@router.delete("/{movimentacao_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(movimentacao_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    movimentacoes.remover(db, movimentacao_id)
