from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.talhao import TalhaoCadastro, TalhaoResposta
from app.services import talhoes as servico

router = APIRouter(tags=["talhões"])

_NOME_DUPLICADO = HTTPException(status.HTTP_409_CONFLICT, "Já existe um talhão com esse nome.")
_TALHAO_INEXISTENTE = HTTPException(status.HTTP_404_NOT_FOUND, "Talhão não encontrado.")


@router.get("/talhoes", response_model=list[TalhaoResposta])
def listar_talhoes(db: Session = Depends(get_db)) -> list[TalhaoResposta]:
    return servico.listar_talhoes(db)


@router.post("/talhoes", response_model=TalhaoResposta, status_code=status.HTTP_201_CREATED)
def criar_talhao(dados: TalhaoCadastro, db: Session = Depends(get_db)) -> TalhaoResposta:
    try:
        return servico.criar_talhao(db, dados)
    except servico.NomeDuplicado:
        raise _NOME_DUPLICADO from None


@router.get("/talhoes/{talhao_id}", response_model=TalhaoResposta)
def detalhar_talhao(talhao_id: int, db: Session = Depends(get_db)) -> TalhaoResposta:
    try:
        return servico.detalhar_talhao(db, talhao_id)
    except servico.TalhaoInexistente:
        raise _TALHAO_INEXISTENTE from None


@router.put("/talhoes/{talhao_id}", response_model=TalhaoResposta)
def atualizar_talhao(
    talhao_id: int, dados: TalhaoCadastro, db: Session = Depends(get_db)
) -> TalhaoResposta:
    try:
        return servico.atualizar_talhao(db, talhao_id, dados)
    except servico.TalhaoInexistente:
        raise _TALHAO_INEXISTENTE from None
    except servico.NomeDuplicado:
        raise _NOME_DUPLICADO from None


@router.delete("/talhoes/{talhao_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_talhao(talhao_id: int, db: Session = Depends(get_db)) -> Response:
    try:
        servico.remover_talhao(db, talhao_id)
    except servico.TalhaoInexistente:
        raise _TALHAO_INEXISTENTE from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
