"""Casos de uso do estoque: cadastro de insumos, movimentações e a análise de cada
insumo a partir do que está no banco."""

from dataclasses import dataclass, replace
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.analysis.consumo import analisar
from app.core.relogio import hoje
from app.domain import estoque as dominio
from app.models import Insumo, Movimentacao
from app.schemas.estoque import (
    AjusteDeInventario,
    ContagemDeInventario,
    InsumoCadastro,
    InsumoDetalhe,
    InsumoResposta,
    MovimentacaoEntrada,
    MovimentacaoResposta,
    PontoDeEstoque,
)

# Campos que vieram depois do site e do app: um PUT que não os manda (de uma versão que
# não os conhece) mantém o que está gravado, em vez de apagá-los.
_CAMPOS_OPCIONAIS_NOVOS = {"embalagem", "pedido_minimo"}
# O que faz dois envios com o mesmo uuid serem o mesmo lançamento. Com as casas que o banco
# guarda: 2,0004 kg vira 2 kg na coluna, e o reenvio de 2,0004 ainda é o mesmo lançamento.
_CONTEUDO_DO_LANCAMENTO = {
    "insumo_id": None,
    "tipo": None,
    "data": None,
    "quantidade": 3,
    "validade": None,
    "motivo": None,
    "valor_unitario": 4,
}


class NomeDuplicado(Exception):
    pass


class InsumoInexistente(Exception):
    pass


class LancamentoDiferente(Exception):
    """O uuid já está num lançamento com outro conteúdo: não é reenvio, é o app usando o
    mesmo identificador para dois lançamentos. Gravar seria perder um deles em silêncio."""

    def __init__(self, campos: list[str]) -> None:
        self.campos = campos
        super().__init__(
            f"Este uuid já identifica outro lançamento, diferente deste em: {', '.join(campos)}. "
            "Cada lançamento precisa de um uuid novo."
        )


@dataclass
class Registro:
    movimentacao: Movimentacao
    nova: bool  # falso quando o uuid já estava gravado: reenvio do app


def listar_insumos(db: Session) -> list[InsumoResposta]:
    insumos = db.scalars(
        select(Insumo).options(selectinload(Insumo.movimentacoes)).order_by(Insumo.nome)
    )
    referencia = hoje()
    return [_resposta(insumo, referencia) for insumo in insumos]


def criar_insumo(db: Session, dados: InsumoCadastro) -> InsumoResposta:
    insumo = Insumo(**dados.model_dump())
    db.add(insumo)
    _salvar(db)
    return _resposta(insumo, hoje())


def atualizar_insumo(db: Session, insumo_id: int, dados: InsumoCadastro) -> InsumoResposta:
    insumo = _buscar_insumo(db, insumo_id)
    for campo, valor in dados.model_dump().items():
        if campo in _CAMPOS_OPCIONAIS_NOVOS and campo not in dados.model_fields_set:
            continue
        setattr(insumo, campo, valor)
    _salvar(db)
    return _resposta(insumo, hoje())


def detalhar_insumo(db: Session, insumo_id: int) -> InsumoDetalhe:
    insumo = _buscar_insumo(db, insumo_id)
    movimentacoes = sorted(insumo.movimentacoes, key=lambda m: (m.data, m.id))
    saldo, por_dia = 0.0, {}
    for m in movimentacoes:
        saldo += m.quantidade if m.tipo == "entrada" else -m.quantidade
        # Vários lançamentos no mesmo dia: vale o saldo depois do último.
        por_dia[m.data] = round(saldo, 3)
    return InsumoDetalhe(
        **dict(_resposta(insumo, hoje())),
        historico=[PontoDeEstoque(data=dia, saldo=valor) for dia, valor in por_dia.items()],
        movimentacoes=[MovimentacaoResposta.model_validate(m) for m in reversed(movimentacoes)],
    )


def remover_insumo(db: Session, insumo_id: int) -> None:
    # As movimentações vão junto pelo ON DELETE CASCADE.
    db.delete(_buscar_insumo(db, insumo_id))
    db.commit()


def listar_movimentacoes(db: Session, insumo_id: int | None, limite: int) -> list[Movimentacao]:
    consulta = select(Movimentacao).order_by(Movimentacao.data.desc(), Movimentacao.id.desc())
    if insumo_id is not None:
        consulta = consulta.where(Movimentacao.insumo_id == insumo_id)
    return list(db.scalars(consulta.limit(limite)))


def registrar_movimentacao(db: Session, dados: MovimentacaoEntrada) -> Registro:
    """Grava o lançamento. Com `uuid` já gravado, é o app reenviando (a resposta anterior se
    perdeu no caminho): devolve o que está no banco, sem gravar de novo."""
    _buscar_insumo(db, dados.insumo_id)
    if dados.uuid is not None and (existente := _pelo_uuid(db, dados.uuid)) is not None:
        return _reenvio(existente, dados)
    movimentacao = Movimentacao(**dados.model_dump())
    db.add(movimentacao)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Dois envios do mesmo lançamento ao mesmo tempo (o app reenviou enquanto o
        # primeiro ainda gravava): o outro chegou antes, e o UNIQUE barrou este. É o mesmo
        # caso do reenvio. Qualquer outra violação segue como erro.
        existente = None if dados.uuid is None else _pelo_uuid(db, dados.uuid)
        if existente is None:
            raise
        return _reenvio(existente, dados)
    # Devolve o que o banco guardou (quantidade em 3 casas), como o reenvio devolverá.
    db.refresh(movimentacao)
    return Registro(movimentacao, nova=True)


def registrar_inventario(
    db: Session, insumo_id: int, contagem: ContagemDeInventario
) -> AjusteDeInventario:
    """Compara a contagem do galpão com o saldo registrado até aquele dia e lança a
    diferença: o estoque passa a ser o que foi contado."""
    insumo = _buscar_insumo(db, insumo_id)
    saldo = round(
        sum(
            m.quantidade if m.tipo == "entrada" else -m.quantidade
            for m in insumo.movimentacoes
            if m.data <= contagem.data
        ),
        3,
    )
    diferenca = round(contagem.quantidade_contada - saldo, 3)
    movimentacao = None
    if diferenca:
        movimentacao = Movimentacao(
            insumo_id=insumo.id,
            tipo="entrada" if diferenca > 0 else "saida",
            motivo="inventario",
            data=contagem.data,
            quantidade=abs(diferenca),
        )
        db.add(movimentacao)
        db.commit()
    return AjusteDeInventario(
        saldo_registrado=saldo,
        quantidade_contada=contagem.quantidade_contada,
        diferenca=diferenca,
        movimentacao=movimentacao and MovimentacaoResposta.model_validate(movimentacao),
    )


def remover_movimentacao(db: Session, movimentacao_id: int) -> bool:
    movimentacao = db.get(Movimentacao, movimentacao_id)
    if movimentacao is None:
        return False
    db.delete(movimentacao)
    db.commit()
    return True


def _pelo_uuid(db: Session, uuid: UUID) -> Movimentacao | None:
    return db.scalar(select(Movimentacao).where(Movimentacao.uuid == uuid))


def _reenvio(existente: Movimentacao, dados: MovimentacaoEntrada) -> Registro:
    diferentes = [
        campo
        for campo, casas in _CONTEUDO_DO_LANCAMENTO.items()
        if _como_no_banco(getattr(existente, campo), casas)
        != _como_no_banco(getattr(dados, campo), casas)
    ]
    if diferentes:
        raise LancamentoDiferente(diferentes)
    return Registro(existente, nova=False)


def _como_no_banco(valor: object, casas: int | None) -> object:
    return round(valor, casas) if casas is not None and isinstance(valor, float) else valor


def _buscar_insumo(db: Session, insumo_id: int) -> Insumo:
    insumo = db.get(Insumo, insumo_id)
    if insumo is None:
        raise InsumoInexistente
    return insumo


def _salvar(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        # A única restrição que a validação do schema não cobre é o nome único.
        raise NomeDuplicado from erro


def _resposta(insumo: Insumo, referencia: date) -> InsumoResposta:
    entradas = [
        dominio.Entrada(m.data, m.quantidade, m.validade, m.valor_unitario)
        for m in insumo.movimentacoes
        if m.tipo == "entrada"
    ]
    # Sobra de inventário não tem preço (o banco nem aceita): só a compra entra no custo.
    custo_medio = dominio.custo_medio(entradas)
    saidas = [m for m in insumo.movimentacoes if m.tipo == "saida"]
    # Só a retirada para uso é consumo; descarte e ajuste de inventário tiram do estoque,
    # mas não do ritmo.
    retiradas = [dominio.Retirada(m.data, m.quantidade) for m in saidas if m.motivo is None]
    descartes = [dominio.Descarte(m.data, m.quantidade) for m in saidas if m.motivo == "descarte"]
    # Produto que faltou na contagem saiu sem registro, como uma retirada: dos lotes bons.
    faltas = [dominio.Retirada(m.data, m.quantidade) for m in saidas if m.motivo == "inventario"]
    # Quantidades têm no máximo 3 casas; arredondar a soma tira o resíduo do float
    # (sem isso, um estoque zerado poderia virar 1e-14 e escapar do alerta).
    estoque = round(sum(e.quantidade for e in entradas) - sum(m.quantidade for m in saidas), 3)
    # Sem movimentação nenhuma, o histórico começa hoje: a análise diz que é curto.
    registros_desde = min((m.data for m in insumo.movimentacoes), default=referencia)

    analise = analisar(
        dominio.Insumo(
            insumo.nome,
            insumo.unidade,
            estoque,
            insumo.estoque_minimo,
            insumo.prazo_reposicao_dias,
            insumo.embalagem,
            insumo.pedido_minimo,
        ),
        retiradas,
        lotes=dominio.lotes_em_estoque(entradas, retiradas + faltas, descartes),
        registros_desde=min(registros_desde, referencia),
        referencia=referencia,
        custo_medio=custo_medio,
    )
    compras = [m for m in insumo.movimentacoes if m.tipo == "entrada" and m.motivo is None]
    com_preco = sum(m.valor_unitario is not None for m in compras)
    if custo_medio is not None and com_preco < len(compras):
        limitacao = (
            f"Custo médio só das compras com preço ({com_preco} de {len(compras)}): as "
            "outras ficam fora da conta."
        )
        analise = replace(analise, limitacoes=[*analise.limitacoes, limitacao])
    if any(e.validade for e in entradas):
        limitacao = (
            "Saldo por lote estimado: as retiradas não dizem de qual lote saíram, então "
            "se supõe que o que vence primeiro é usado primeiro."
        )
        analise = replace(analise, limitacoes=[*analise.limitacoes, limitacao])
    if any(m.motivo == "inventario" for m in insumo.movimentacoes):
        limitacao = (
            "Houve ajuste de inventário: a diferença da contagem corrige o estoque, mas não "
            "entra no ritmo de consumo, porque não se sabe quando o produto saiu."
        )
        analise = replace(analise, limitacoes=[*analise.limitacoes, limitacao])
    return InsumoResposta(
        id=insumo.id,
        demonstracao=insumo.demonstracao,
        nome=insumo.nome,
        unidade=insumo.unidade,
        estoque_minimo=insumo.estoque_minimo,
        prazo_reposicao_dias=insumo.prazo_reposicao_dias,
        embalagem=insumo.embalagem,
        pedido_minimo=insumo.pedido_minimo,
        estoque_atual=estoque,
        custo_medio=None if custo_medio is None else round(custo_medio, 4),
        # Estoque negativo é registro faltando, não dívida: vale zero.
        valor_em_estoque=None if custo_medio is None else round(max(estoque, 0) * custo_medio, 2),
        analise=analise,
    )
