import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.erros import RESPOSTAS_DE_ERRO
from app.core.database import get_db
from app.schemas.insumo import InsumoEntrada, InsumoSaida
from app.services import insumos

router = APIRouter(prefix="/insumos", tags=["insumos"], responses=RESPOSTAS_DE_ERRO)


@router.get("", response_model=list[InsumoSaida])
def listar(db: Session = Depends(get_db)) -> list[InsumoSaida]:
    return insumos.listar(db)


@router.post("", response_model=InsumoSaida, status_code=status.HTTP_201_CREATED)
def criar(dados: InsumoEntrada, db: Session = Depends(get_db)) -> InsumoSaida:
    return insumos.criar(db, dados)


@router.get("/{insumo_id}", response_model=InsumoSaida)
def obter(insumo_id: uuid.UUID, db: Session = Depends(get_db)) -> InsumoSaida:
    return insumos.obter(db, insumo_id)


@router.put("/{insumo_id}", response_model=InsumoSaida)
def atualizar(
    insumo_id: uuid.UUID, dados: InsumoEntrada, db: Session = Depends(get_db)
) -> InsumoSaida:
    return insumos.atualizar(db, insumo_id, dados)


@router.delete("/{insumo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(insumo_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    insumos.remover(db, insumo_id)
