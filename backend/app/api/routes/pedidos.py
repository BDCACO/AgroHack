from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.permissoes import origem_do_pedido, usuario_atual
from app.core.database import get_db
from app.models import Usuario
from app.schemas.compras import (
    PedidoEntrada,
    PedidoResposta,
    Recebimento,
    ResultadoDoRecebimento,
    Situacao,
    SugestaoDePedido,
)
from app.services import pedidos as servico
from app.services import sugestao_de_pedido
from app.services.auditoria import Origem

# O funcionário consulta os pedidos e recebe a carga (é ele quem confere no galpão o que
# chegou); o dono faz, altera e cancela, porque é quem compra e paga.
campo = APIRouter(tags=["pedidos"])
gestao = APIRouter(tags=["pedidos"])

_INEXISTENTE = HTTPException(status.HTTP_404_NOT_FOUND, "Pedido não encontrado.")


@campo.get("/pedidos", response_model=list[PedidoResposta])
def listar_pedidos(
    situacao: Situacao | None = None,
    fornecedor_id: int | None = None,
    insumo_id: int | None = None,
    limite: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[PedidoResposta]:
    """Os mais recentes primeiro, com o que já chegou e o que falta de cada linha."""
    return servico.listar_pedidos(db, situacao, fornecedor_id, insumo_id, limite)


# Antes de /pedidos/{pedido_id}: senão "sugestao" seria lido como o id de um pedido.
@campo.get("/pedidos/sugestao", response_model=SugestaoDePedido)
def sugerir_pedido(
    dias: int = Query(7, ge=0, le=90), db: Session = Depends(get_db)
) -> SugestaoDePedido:
    """As reposições para pedir hoje ou nos próximos `dias`, agrupadas pelo fornecedor da
    última compra de cada insumo, com a quantidade (já descontado o que está a caminho) e o
    preço estimado. Cada grupo, confirmado, vai para POST /pedidos."""
    return sugestao_de_pedido.sugerir(db, dias)


@gestao.post("/pedidos", response_model=PedidoResposta, status_code=status.HTTP_201_CREATED)
def criar_pedido(
    dados: PedidoEntrada,
    db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(usuario_atual),
) -> PedidoResposta:
    """O pedido feito à revenda. Enquanto não chega, o que falta entra na análise de cada
    insumo (`em_pedido`): a reposição o desconta."""
    try:
        return servico.criar_pedido(db, dados, None if usuario is None else usuario.id)
    except servico.DadoInvalido as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None


@campo.get("/pedidos/{pedido_id}", response_model=PedidoResposta)
def detalhar_pedido(pedido_id: int, db: Session = Depends(get_db)) -> PedidoResposta:
    try:
        return servico.detalhar_pedido(db, pedido_id)
    except servico.PedidoInexistente:
        raise _INEXISTENTE from None


@gestao.put("/pedidos/{pedido_id}", response_model=PedidoResposta)
def atualizar_pedido(
    pedido_id: int,
    dados: PedidoEntrada,
    db: Session = Depends(get_db),
    origem: Origem = Depends(origem_do_pedido),
) -> PedidoResposta:
    """Só o pedido aberto, antes de chegar qualquer coisa (senão `409`). Muda os campos
    enviados e troca as linhas pelas do corpo."""
    try:
        return servico.atualizar_pedido(db, pedido_id, dados, origem)
    except servico.PedidoInexistente:
        raise _INEXISTENTE from None
    except servico.PedidoFechado as erro:
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro)) from None
    except servico.DadoInvalido as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None


@gestao.post("/pedidos/{pedido_id}/cancelar", response_model=PedidoResposta)
def cancelar_pedido(
    pedido_id: int, db: Session = Depends(get_db), origem: Origem = Depends(origem_do_pedido)
) -> PedidoResposta:
    """O que falta chegar não vem mais; o que já chegou fica no estoque. O pedido que chegou
    inteiro não se cancela (`409`)."""
    try:
        return servico.cancelar_pedido(db, pedido_id, origem)
    except servico.PedidoInexistente:
        raise _INEXISTENTE from None
    except servico.PedidoFechado as erro:
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro)) from None


@campo.post("/pedidos/{pedido_id}/receber", response_model=ResultadoDoRecebimento)
def receber_pedido(
    pedido_id: int,
    dados: Recebimento,
    db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(usuario_atual),
) -> ResultadoDoRecebimento:
    """A carga que chegou (`data`, padrão hoje, nunca futura): cada linha vira uma entrada
    no estoque, com o fornecedor, o preço (o combinado, ou o da nota se mudou), a validade e
    quem conferiu, e o pedido passa a `parcial` ou `recebido`, numa transação só. O que
    veio a mais entra, com aviso. Pedido cancelado ou já recebido é `409`."""
    try:
        return servico.receber_pedido(db, pedido_id, dados, None if usuario is None else usuario.id)
    except servico.PedidoInexistente:
        raise _INEXISTENTE from None
    except servico.PedidoFechado as erro:
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro)) from None
    except servico.DadoInvalido as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None
