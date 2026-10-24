from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.permissoes import origem_do_pedido
from app.core.database import get_db
from app.models import Fornecedor
from app.schemas.compras import FornecedorCadastro, FornecedorDetalhe, FornecedorResposta
from app.services import fornecedores as servico
from app.services.auditoria import Origem

# O funcionário consulta (confere de quem é a carga que chegou, liga para a revenda); o
# dono cadastra, altera e remove.
campo = APIRouter(tags=["fornecedores"])
gestao = APIRouter(tags=["fornecedores"])

_NOME_DUPLICADO = HTTPException(status.HTTP_409_CONFLICT, "Já existe um fornecedor com esse nome.")
_INEXISTENTE = HTTPException(status.HTTP_404_NOT_FOUND, "Fornecedor não encontrado.")


@campo.get("/fornecedores", response_model=list[FornecedorResposta])
def listar_fornecedores(db: Session = Depends(get_db)) -> list[Fornecedor]:
    """Todos, os desativados também (`ativo`): as compras antigas apontam para eles."""
    return servico.listar_fornecedores(db)


@gestao.post(
    "/fornecedores", response_model=FornecedorResposta, status_code=status.HTTP_201_CREATED
)
def criar_fornecedor(dados: FornecedorCadastro, db: Session = Depends(get_db)) -> Fornecedor:
    try:
        return servico.criar_fornecedor(db, dados)
    except servico.NomeDuplicado:
        raise _NOME_DUPLICADO from None


@campo.get("/fornecedores/{fornecedor_id}", response_model=FornecedorDetalhe)
def detalhar_fornecedor(fornecedor_id: int, db: Session = Depends(get_db)) -> FornecedorDetalhe:
    """O fornecedor, as compras recentes e o preço médio pago a ele por insumo, para
    comparar com as outras revendas."""
    try:
        return servico.detalhar_fornecedor(db, fornecedor_id)
    except servico.FornecedorInexistente:
        raise _INEXISTENTE from None


@gestao.put("/fornecedores/{fornecedor_id}", response_model=FornecedorResposta)
def atualizar_fornecedor(
    fornecedor_id: int,
    dados: FornecedorCadastro,
    db: Session = Depends(get_db),
    origem: Origem = Depends(origem_do_pedido),
) -> Fornecedor:
    """Muda só os campos enviados: `{"nome": ..., "ativo": false}` desativa sem apagar o
    resto."""
    try:
        return servico.atualizar_fornecedor(db, fornecedor_id, dados, origem)
    except servico.FornecedorInexistente:
        raise _INEXISTENTE from None
    except servico.NomeDuplicado:
        raise _NOME_DUPLICADO from None


@gestao.delete("/fornecedores/{fornecedor_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_fornecedor(
    fornecedor_id: int, db: Session = Depends(get_db), origem: Origem = Depends(origem_do_pedido)
) -> Response:
    """Só o fornecedor cadastrado por engano, sem compra nem pedido: com história, `409`
    (desative-o)."""
    try:
        servico.remover_fornecedor(db, fornecedor_id, origem)
    except servico.FornecedorInexistente:
        raise _INEXISTENTE from None
    except servico.FornecedorComHistoria as erro:
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro)) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
