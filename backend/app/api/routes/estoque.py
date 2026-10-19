from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.estoque import (
    InsumoCadastro,
    InsumoResposta,
    MovimentacaoEntrada,
    MovimentacaoResposta,
    PedidoDeImportacao,
)
from app.services import estoque as servico
from app.services.importacao import ResultadoImportacao, importar

router = APIRouter(tags=["estoque"])

_NOME_DUPLICADO = HTTPException(status.HTTP_409_CONFLICT, "Já existe um insumo com esse nome.")
_INSUMO_INEXISTENTE = "Insumo não encontrado."


@router.get("/insumos", response_model=list[InsumoResposta])
def listar_insumos(db: Session = Depends(get_db)) -> list[InsumoResposta]:
    """Cada insumo com o estoque atual e a análise na data de hoje (Rondônia)."""
    return servico.listar_insumos(db)


@router.post("/insumos", response_model=InsumoResposta, status_code=status.HTTP_201_CREATED)
def criar_insumo(dados: InsumoCadastro, db: Session = Depends(get_db)) -> InsumoResposta:
    try:
        return servico.criar_insumo(db, dados)
    except servico.NomeDuplicado:
        raise _NOME_DUPLICADO from None


@router.put("/insumos/{insumo_id}", response_model=InsumoResposta)
def atualizar_insumo(
    insumo_id: int, dados: InsumoCadastro, db: Session = Depends(get_db)
) -> InsumoResposta:
    try:
        return servico.atualizar_insumo(db, insumo_id, dados)
    except servico.InsumoInexistente:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _INSUMO_INEXISTENTE) from None
    except servico.NomeDuplicado:
        raise _NOME_DUPLICADO from None


@router.get("/movimentacoes", response_model=list[MovimentacaoResposta])
def listar_movimentacoes(
    insumo_id: int | None = None,
    limite: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[MovimentacaoResposta]:
    """As mais recentes primeiro."""
    return servico.listar_movimentacoes(db, insumo_id, limite)


@router.post(
    "/movimentacoes", response_model=MovimentacaoResposta, status_code=status.HTTP_201_CREATED
)
def registrar_movimentacao(
    dados: MovimentacaoEntrada, db: Session = Depends(get_db)
) -> MovimentacaoResposta:
    try:
        return servico.registrar_movimentacao(db, dados)
    except servico.InsumoInexistente:
        # 422, não 404: o recurso da URL existe; o que está errado é o corpo.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _INSUMO_INEXISTENTE) from None


@router.delete("/movimentacoes/{movimentacao_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_movimentacao(movimentacao_id: int, db: Session = Depends(get_db)) -> Response:
    """Para corrigir lançamento errado: remove e lança de novo."""
    if not servico.remover_movimentacao(db, movimentacao_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Movimentação não encontrada.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/importacoes", response_model=ResultadoImportacao)
def importar_planilha(
    pedido: PedidoDeImportacao, db: Session = Depends(get_db)
) -> ResultadoImportacao:
    """Movimentações de uma planilha CSV (data, insumo, unidade, tipo, quantidade,
    validade). Sem `confirmar`, só confere e resume. Com um erro sequer, nada é
    gravado: a resposta lista os erros por linha e `importado` vem falso."""
    return importar(db, pedido.conteudo, confirmar=pedido.confirmar)
