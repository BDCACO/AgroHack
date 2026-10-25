"""Casos de uso dos pedidos de compra: o que foi pedido à revenda e o que já chegou.

O ciclo é sugerido → pedido → recebido. Enquanto não chega, o que falta de cada pedido
aberto ou parcial entra na análise do insumo (`estoque.a_caminho`): sem isso, a reposição
mandaria comprar de novo o que está a caminho.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.relogio import hoje
from app.domain.estoque import quantidade_legivel
from app.models import Fornecedor, Insumo, ItemDoPedido, Movimentacao, Pedido
from app.schemas.compras import (
    ItemDoPedidoResposta,
    PedidoAlteracao,
    PedidoEntrada,
    PedidoResposta,
    Recebimento,
    ResultadoDoRecebimento,
    Situacao,
)
from app.schemas.estoque import MovimentacaoResposta
from app.services import auditoria

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
    limite: int | None = 200,
) -> list[PedidoResposta]:
    """Os mais recentes primeiro. `limite=None` traz todos: o relatório em Excel não pode
    deixar de fora os mais antigos, que são os mais atrasados."""
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


def atualizar_pedido(
    db: Session, pedido_id: int, dados: PedidoAlteracao, origem: auditoria.Origem
) -> PedidoResposta:
    """Só enquanto nada chegou: depois, as entradas já gravadas apontam para as linhas, e
    mudar o pedido as deixaria contando outra história. Muda os campos enviados e troca as
    linhas pelas do corpo; a linha do mesmo insumo é a mesma, com a quantidade nova."""
    pedido = buscar_pedido(db, pedido_id, travar=True)
    if pedido.situacao != "aberto" or any(i.quantidade_recebida for i in pedido.itens):
        raise PedidoFechado(
            f"Este pedido está {_SITUACOES[pedido.situacao]}: só se altera o pedido aberto, "
            "antes de chegar qualquer coisa. Faça um pedido novo."
        )
    _conferir(db, dados, fornecedor_atual=pedido.fornecedor_id)
    antes = _combinado(pedido)
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
    # O que a revenda vai entregar, e quanto vai cobrar: quem mudou fica na trilha.
    if mudou := auditoria.diferencas(antes, _combinado(pedido)):
        auditoria.registrar(db, origem, "pedido.alterado", "pedido", pedido.id, mudou)
    db.commit()
    db.refresh(pedido)
    return resposta(pedido, hoje())


def cancelar_pedido(db: Session, pedido_id: int, origem: auditoria.Origem) -> PedidoResposta:
    """O que falta chegar não vem mais. O que já chegou fica: está no galpão e no estoque.
    Cancelar de novo não muda nada (o app pode reenviar), e não deixa outro evento."""
    pedido = buscar_pedido(db, pedido_id, travar=True)
    if pedido.situacao == "recebido":
        raise PedidoFechado(
            "Este pedido já chegou inteiro: não há o que cancelar. Se algo veio errado, "
            "lance a devolução como descarte."
        )
    if pedido.situacao != "cancelado":
        # O que faltava chegar de cada linha: é o que deixou de vir, e a análise deixou de
        # descontar.
        auditoria.registrar(
            db,
            origem,
            "pedido.cancelado",
            "pedido",
            pedido.id,
            {
                "situacao_antes": pedido.situacao,
                "fornecedor_id": pedido.fornecedor_id,
                "fornecedor": None if pedido.fornecedor is None else pedido.fornecedor.nome,
                "feito_em": pedido.feito_em,
                "previsto_para": pedido.previsto_para,
                "itens": [
                    {
                        "insumo_id": item.insumo_id,
                        "insumo": item.insumo.nome,
                        "quantidade": item.quantidade,
                        "valor_unitario": item.valor_unitario,
                        "quantidade_recebida": item.quantidade_recebida,
                        "falta_receber": item.falta_receber,
                    }
                    for item in pedido.itens
                ],
            },
        )
    pedido.situacao = "cancelado"
    db.commit()
    return resposta(pedido, hoje())


def receber_pedido(
    db: Session, pedido_id: int, dados: Recebimento, usuario_id: int | None
) -> ResultadoDoRecebimento:
    """A carga chegou: cada linha recebida vira uma entrada (com o fornecedor do pedido, o
    preço combinado ou o da nota, a validade e quem conferiu), e o pedido passa a parcial
    ou recebido. Tudo numa transação: ou entra a carga inteira, ou nada.

    O que veio a mais que o pedido entra, com aviso: está no galpão, e recusar deixaria o
    estoque menor que o real."""
    pedido = buscar_pedido(db, pedido_id, travar=True)
    if pedido.situacao == "cancelado":
        raise PedidoFechado(
            "Este pedido está cancelado: não há o que receber. Se a carga chegou mesmo assim, "
            "lance a entrada como uma compra."
        )
    if pedido.situacao == "recebido":
        raise PedidoFechado("Este pedido já chegou inteiro: lance a carga a mais como uma compra.")
    if dados.data < pedido.feito_em:
        raise DadoInvalido(
            f"A carga não chega antes do pedido: o pedido é de {pedido.feito_em:%d/%m/%Y}."
        )
    linhas = {item.id: item for item in pedido.itens}
    for recebido in dados.itens:
        if recebido.item_id not in linhas:
            raise DadoInvalido(f"A linha {recebido.item_id} não é deste pedido.")

    entradas, avisos = [], []
    for recebido in dados.itens:
        item = linhas[recebido.item_id]
        preco = recebido.valor_unitario
        entrada = Movimentacao(
            insumo_id=item.insumo_id,
            tipo="entrada",
            data=dados.data,
            quantidade=recebido.quantidade,
            validade=recebido.validade,
            valor_unitario=item.valor_unitario if preco is None else preco,
            fornecedor_id=pedido.fornecedor_id,
            item_do_pedido_id=item.id,
            usuario_id=usuario_id,
        )
        db.add(entrada)
        entradas.append(entrada)
        item.quantidade_recebida = round(item.quantidade_recebida + recebido.quantidade, 3)
        if item.quantidade_recebida > item.quantidade:
            unidade = item.insumo.unidade
            avisos.append(
                f"Chegaram {quantidade_legivel(item.quantidade_recebida, unidade)} de "
                f"{item.insumo.nome}, "
                f"{quantidade_legivel(item.quantidade_recebida - item.quantidade, unidade)} a "
                f"mais que o pedido ({quantidade_legivel(item.quantidade, unidade)}): confira a "
                "nota."
            )
    pedido.situacao = situacao_pelo_recebido(pedido)
    db.commit()
    for entrada in entradas:
        # O que o banco guardou (quantidade em 3 casas), com quem lançou e o fornecedor.
        db.refresh(entrada)
    return ResultadoDoRecebimento(
        pedido=resposta(pedido, hoje()),
        movimentacoes=[MovimentacaoResposta.model_validate(e) for e in entradas],
        avisos=avisos,
    )


def situacao_pelo_recebido(pedido: Pedido) -> str:
    """Aberto, parcial ou recebido, pelo que já chegou de cada linha. O cancelado continua
    cancelado: o que faltava não vem mais, chegue o que chegar."""
    if pedido.situacao == "cancelado":
        return "cancelado"
    if all(item.quantidade_recebida >= item.quantidade for item in pedido.itens):
        return "recebido"
    if any(item.quantidade_recebida for item in pedido.itens):
        return "parcial"
    return "aberto"


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


def _combinado(pedido: Pedido) -> dict[str, object]:
    """O que se combinou com a revenda: o que se compara numa alteração. As linhas pelo
    insumo, para a ordem em que foram gravadas não parecer mudança."""
    return {
        "fornecedor_id": pedido.fornecedor_id,
        "feito_em": pedido.feito_em,
        "previsto_para": pedido.previsto_para,
        "observacao": pedido.observacao,
        "itens": sorted(
            (
                {
                    "insumo_id": item.insumo_id,
                    "quantidade": item.quantidade,
                    "valor_unitario": item.valor_unitario,
                }
                for item in pedido.itens
            ),
            key=lambda item: item["insumo_id"],
        ),
    }


def _conferir(db: Session, dados: PedidoEntrada, fornecedor_atual: int | None = None) -> None:
    """`fornecedor_atual`: o do pedido que se altera. Ativo, o fornecedor só precisa estar
    quando muda: o site reenvia o pedido inteiro, e o fornecedor desativado depois do pedido
    não pode travar a mudança da previsão ou das quantidades."""
    if dados.fornecedor_id is not None:
        fornecedor = db.get(Fornecedor, dados.fornecedor_id)
        if fornecedor is None:
            raise DadoInvalido("Fornecedor não encontrado.")
        if not fornecedor.ativo and fornecedor.id != fornecedor_atual:
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
