from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.categoria import CategoriaCadastro, CategoriaResposta
from app.services import categorias as servico

# Como os talhões: o funcionário lê (para filtrar a lista de insumos); o dono cadastra,
# altera e remove.
campo = APIRouter(tags=["categorias"])
gestao = APIRouter(tags=["categorias"])

_NOME_DUPLICADO = HTTPException(status.HTTP_409_CONFLICT, "Já existe uma categoria com esse nome.")
_INEXISTENTE = HTTPException(status.HTTP_404_NOT_FOUND, "Categoria não encontrada.")


@campo.get("/categorias", response_model=list[CategoriaResposta])
def listar_categorias(db: Session = Depends(get_db)) -> list[CategoriaResposta]:
    """Pelo nome, cada uma com quantos insumos tem."""
    return servico.listar_categorias(db)


@gestao.post("/categorias", response_model=CategoriaResposta, status_code=status.HTTP_201_CREATED)
def criar_categoria(dados: CategoriaCadastro, db: Session = Depends(get_db)) -> CategoriaResposta:
    try:
        return servico.criar_categoria(db, dados)
    except servico.NomeDuplicado:
        raise _NOME_DUPLICADO from None


@gestao.put("/categorias/{categoria_id}", response_model=CategoriaResposta)
def atualizar_categoria(
    categoria_id: int, dados: CategoriaCadastro, db: Session = Depends(get_db)
) -> CategoriaResposta:
    try:
        return servico.atualizar_categoria(db, categoria_id, dados)
    except servico.CategoriaInexistente:
        raise _INEXISTENTE from None
    except servico.NomeDuplicado:
        raise _NOME_DUPLICADO from None


@gestao.delete("/categorias/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_categoria(categoria_id: int, db: Session = Depends(get_db)) -> Response:
    """Só a categoria sem insumo: com algum, `409` (mude-os de categoria antes)."""
    try:
        servico.remover_categoria(db, categoria_id)
    except servico.CategoriaInexistente:
        raise _INEXISTENTE from None
    except servico.CategoriaComInsumos as erro:
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro)) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
