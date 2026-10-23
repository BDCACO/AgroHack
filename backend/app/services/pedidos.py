"""Casos de uso dos pedidos de compra: o que foi pedido à revenda e o que já chegou.

O ciclo é sugerido → pedido → recebido. Enquanto não chega, o que falta de cada pedido
aberto ou parcial entra na análise do insumo (`estoque.a_caminho`): sem isso, a reposição
mandaria comprar de novo o que está a caminho.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.relogio import hoje
from app.models import Fornecedor, Insumo, ItemDoPedido, Pedido
from app.schemas.compras import (
    ItemDoPedidoResposta,
    PedidoEntrada,
    PedidoResposta,
    Situacao,
)

# Situações em que ainda falta chegar alguma coisa.
EM_ANDAMENTO = ("aberto", "parcial")


class PedidoInexistente(Exception):
    pass


class DadoInvalido(Exception):
    """O corpo aponta para o que não existe ou não pode ser usado: 422 com a frase."""


class PedidoFechado(Exception):
    """A situação do pedido não permite o que se pediu: 409 com a frase."""


def listar_pedidos(
    db: Session,
    situacao: Situacao | None = None,
    fornecedor_id: int | None = None,
    insumo_id: int | None = None,
    limite: int = 200,
) -> list[PedidoResposta]:
    """Os mais recentes primeiro."""
    consulta = select(Pedido).order_by(Pedido.feito_em.desc(), Pedido.id.desc())
    if situacao is not None:
        consulta = consulta.where(Pedido.situacao == situacao)
    if fornecedor_id is not None:
        consulta = consulta.where(Pedido.fornecedor_id == fornecedor_id)
    if insumo_id is not None:
        consulta = consulta.where(Pedido.itens.any(ItemDoPedido.insumo_id == insumo_id))
    referencia = hoje()
    return [resposta(p, referencia) for p in db.scalars(consulta.limit(limite)).unique()]


def criar_pedido(db: Session, dados: PedidoEntrada, usuario_id: int | None) -> PedidoResposta:
    _conferir(db, dados)
    pedido = Pedido(
        fornecedor_id=dados.fornecedor_id,
        situacao="aberto",
        feito_em=dados.feito_em,
        previsto_para=dados.previsto_para,
        observacao=dados.observacao,
        usuario_id=usuario_id,
        itens=[ItemDoPedido(**item.model_dump()) for item in dados.itens],
    )
    db.add(pedido)
    db.commit()
    db.refresh(pedido)
    return resposta(pedido, hoje())


def detalhar_pedido(db: Session, pedido_id: int) -> PedidoResposta:
    return resposta(buscar_pedido(db, pedido_id), hoje())


def atualizar_pedido(db: Session, pedido_id: int, dados: PedidoEntrada) -> PedidoResposta:
    """Só enquanto nada chegou: depois, as entradas já gravadas apontam para as linhas, e
    mudar o pedido as deixaria contando outra história. Muda os campos enviados e troca as
    linhas pelas do corpo; a linha do mesmo insumo é a mesma, com a quantidade nova."""
    pedido = buscar_pedido(db, pedido_id, travar=True)
    if pedido.situacao != "aberto" or any(i.quantidade_recebida for i in pedido.itens):
        raise PedidoFechado(
            f"Este pedido está {_SITUACOES[pedido.situacao]}: só se altera o pedido aberto, "
            "antes de chegar qualquer coisa. Faça um pedido novo."
        )
    _conferir(db, dados)
    for campo in ("fornecedor_id", "feito_em", "previsto_para", "observacao"):
        if campo in dados.model_fields_set:
            setattr(pedido, campo, getattr(dados, campo))
    if pedido.previsto_para is not None and pedido.previsto_para < pedido.feito_em:
        raise DadoInvalido("A previsão de chegada não pode ser antes do pedido.")
    atuais = {item.insumo_id: item for item in pedido.itens}
    novos = {item.insumo_id: item for item in dados.itens}
    for insumo_id, item in atuais.items():
        if insumo_id not in novos:
            pedido.itens.remove(item)
    # Remove antes de inserir: o UNIQUE (pedido, insumo) não vê duas linhas do mesmo insumo.
    db.flush()
    for insumo_id, novo in novos.items():
        if insumo_id in atuais:
            atuais[insumo_id].quantidade = novo.quantidade
            atuais[insumo_id].valor_unitario = novo.valor_unitario
        else:
            pedido.itens.append(ItemDoPedido(**novo.model_dump()))
    db.commit()
    db.refresh(pedido)
    return resposta(pedido, hoje())


def cancelar_pedido(db: Session, pedido_id: int) -> PedidoResposta:
    """O que falta chegar não vem mais. O que já chegou fica: está no galpão e no estoque.
    Cancelar de novo não muda nada (o app pode reenviar)."""
    pedido = buscar_pedido(db, pedido_id, travar=True)
    if pedido.situacao == "recebido":
        raise PedidoFechado(
            "Este pedido já chegou inteiro: não há o que cancelar. Se algo veio errado, "
            "lance a devolução como descarte."
        )
    pedido.situacao = "cancelado"
    db.commit()
    return resposta(pedido, hoje())


def buscar_pedido(db: Session, pedido_id: int, *, travar: bool = False) -> Pedido:
    """Com `travar`, segura a linha do pedido até o fim da transação: dois recebimentos (ou
    um recebimento e um cancelamento) ao mesmo tempo entram um de cada vez."""
    consulta = select(Pedido).where(Pedido.id == pedido_id)
    if travar:
        consulta = consulta.with_for_update(of=Pedido)
    pedido = db.scalars(consulta).unique().one_or_none()
    if pedido is None:
        raise PedidoInexistente
    return pedido


def resposta(pedido: Pedido, referencia: date) -> PedidoResposta:
    itens = [
        ItemDoPedidoResposta(
            id=item.id,
            insumo_id=item.insumo_id,
            insumo=item.insumo.nome,
            unidade=item.insumo.unidade,
            quantidade=item.quantidade,
            valor_unitario=item.valor_unitario,
            quantidade_recebida=item.quantidade_recebida,
            falta_receber=item.falta_receber,
        )
        for item in pedido.itens
    ]
    com_preco = [i for i in itens if i.valor_unitario is not None]
    return PedidoResposta(
        id=pedido.id,
        fornecedor_id=pedido.fornecedor_id,
        fornecedor=None if pedido.fornecedor is None else pedido.fornecedor.nome,
        situacao=pedido.situacao,
        feito_em=pedido.feito_em,
        previsto_para=pedido.previsto_para,
        observacao=pedido.observacao,
        usuario_id=pedido.usuario_id,
        feito_por=None if pedido.usuario is None else pedido.usuario.nome,
        atrasado=pedido.situacao in EM_ANDAMENTO
        and pedido.previsto_para is not None
        and pedido.previsto_para < referencia,
        custo_estimado=(
            round(sum(i.quantidade * i.valor_unitario for i in com_preco), 2) if com_preco else None
        ),
        itens=itens,
    )


def _conferir(db: Session, dados: PedidoEntrada) -> None:
    if dados.fornecedor_id is not None:
        fornecedor = db.get(Fornecedor, dados.fornecedor_id)
        if fornecedor is None:
            raise DadoInvalido("Fornecedor não encontrado.")
        if not fornecedor.ativo:
            raise DadoInvalido(
                f"{fornecedor.nome} está desativado: reative-o na tela de Fornecedores para "
                "fazer um pedido a ele."
            )
    pedidos = {item.insumo_id for item in dados.itens}
    existentes = set(db.scalars(select(Insumo.id).where(Insumo.id.in_(pedidos))))
    if faltando := sorted(pedidos - existentes):
        raise DadoInvalido(f"Insumo {faltando[0]} não encontrado.")


_SITUACOES = {
    "aberto": "aberto",
    "parcial": "com parte recebida",
    "recebido": "recebido",
    "cancelado": "cancelado",
}
