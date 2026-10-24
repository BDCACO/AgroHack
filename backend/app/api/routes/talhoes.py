from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.permissoes import origem_do_pedido
from app.core.database import get_db
from app.schemas.talhao import TalhaoCadastro, TalhaoDetalhe, TalhaoResposta
from app.services import talhoes as servico
from app.services.auditoria import Origem

# Como no estoque: o funcionário consulta os talhões (para lançar a aplicação no certo); o
# dono cadastra, altera e remove.
campo = APIRouter(tags=["talhões"])
gestao = APIRouter(tags=["talhões"])

_NOME_DUPLICADO = HTTPException(status.HTTP_409_CONFLICT, "Já existe um talhão com esse nome.")
_TALHAO_INEXISTENTE = HTTPException(status.HTTP_404_NOT_FOUND, "Talhão não encontrado.")


class Periodo:
    """Recorte do custo (uma safra): `desde` e `ate`, os dois inclusive e opcionais. A
    carência não depende dele."""

    def __init__(self, desde: date | None = None, ate: date | None = None) -> None:
        if desde is not None and ate is not None and desde > ate:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "O período começa depois de terminar: troque as datas.",
            )
        self.desde, self.ate = desde, ate


@campo.get("/talhoes", response_model=list[TalhaoResposta])
def listar_talhoes(
    periodo: Periodo = Depends(), db: Session = Depends(get_db)
) -> list[TalhaoResposta]:
    """Cada talhão com a carência de hoje (até quando não colher, com a conta) e o custo do
    que foi aplicado nele no período, total e por hectare, com as limitações."""
    return servico.listar_talhoes(db, periodo.desde, periodo.ate)


@gestao.post("/talhoes", response_model=TalhaoResposta, status_code=status.HTTP_201_CREATED)
def criar_talhao(dados: TalhaoCadastro, db: Session = Depends(get_db)) -> TalhaoResposta:
    try:
        return servico.criar_talhao(db, dados)
    except servico.NomeDuplicado:
        raise _NOME_DUPLICADO from None


@campo.get("/talhoes/{talhao_id}", response_model=TalhaoDetalhe)
def detalhar_talhao(
    talhao_id: int, periodo: Periodo = Depends(), db: Session = Depends(get_db)
) -> TalhaoDetalhe:
    """O talhão, as aplicações do período (as mais recentes primeiro) e o consumo de cada
    insumo nele."""
    try:
        return servico.detalhar_talhao(db, talhao_id, periodo.desde, periodo.ate)
    except servico.TalhaoInexistente:
        raise _TALHAO_INEXISTENTE from None


@gestao.put("/talhoes/{talhao_id}", response_model=TalhaoResposta)
def atualizar_talhao(
    talhao_id: int,
    dados: TalhaoCadastro,
    db: Session = Depends(get_db),
    origem: Origem = Depends(origem_do_pedido),
) -> TalhaoResposta:
    try:
        return servico.atualizar_talhao(db, talhao_id, dados, origem)
    except servico.TalhaoInexistente:
        raise _TALHAO_INEXISTENTE from None
    except servico.NomeDuplicado:
        raise _NOME_DUPLICADO from None


@gestao.delete("/talhoes/{talhao_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_talhao(
    talhao_id: int, db: Session = Depends(get_db), origem: Origem = Depends(origem_do_pedido)
) -> Response:
    """Só o talhão sem aplicação: com alguma, `409`, para não perder onde cada insumo foi."""
    try:
        servico.remover_talhao(db, talhao_id, origem)
    except servico.TalhaoInexistente:
        raise _TALHAO_INEXISTENTE from None
    except servico.TalhaoComAplicacoes as erro:
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro)) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
