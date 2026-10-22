"""Casos de uso dos talhões: o cadastro, e a carência e o custo do que foi aplicado em
cada um, a partir das retiradas lançadas nele."""

from collections import defaultdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.relogio import hoje
from app.domain import estoque as dominio
from app.domain import talhao as regras
from app.models import Insumo, Movimentacao, Talhao
from app.schemas.estoque import MovimentacaoResposta
from app.schemas.talhao import TalhaoCadastro, TalhaoDetalhe, TalhaoResposta


class NomeDuplicado(Exception):
    pass


class TalhaoInexistente(Exception):
    pass


class TalhaoComAplicacoes(Exception):
    """Remover o talhão apagaria (ou deixaria sem dono) o registro de onde cada insumo foi
    aplicado: a rastreabilidade que a carência e o custo usam."""

    def __init__(self, nome: str, aplicacoes: int) -> None:
        quantas = (
            "1 aplicação registrada" if aplicacoes == 1 else f"{aplicacoes} aplicações registradas"
        )
        super().__init__(
            f"{nome} tem {quantas}: removê-lo apagaria para onde foi cada insumo. Remova as "
            "aplicações antes, se foram lançadas por engano."
        )


def listar_talhoes(
    db: Session, desde: date | None = None, ate: date | None = None
) -> list[TalhaoResposta]:
    """Cada talhão com a carência de hoje e o custo do período (`desde` e `ate` inclusive;
    sem eles, desde sempre)."""
    referencia = hoje()
    aplicacoes = _aplicacoes(db)
    custos = _custos_medios(db)
    return [
        _resposta(talhao, aplicacoes.get(talhao.id, []), custos, referencia, desde, ate)
        for talhao in db.scalars(select(Talhao).order_by(Talhao.nome))
    ]


def detalhar_talhao(
    db: Session, talhao_id: int, desde: date | None = None, ate: date | None = None
) -> TalhaoDetalhe:
    """O talhão, as aplicações do período (as mais recentes primeiro) e quanto de cada
    insumo foi para ele."""
    talhao = buscar_talhao(db, talhao_id)
    aplicacoes = _aplicacoes(db, talhao_id).get(talhao_id, [])
    custos = _custos_medios(db)
    no_periodo = sorted(
        (m for m, _ in aplicacoes if _no_periodo(m.data, desde, ate)),
        key=lambda m: (m.data, m.id),
        reverse=True,
    )
    custo = regras.custo([a for _, a in aplicacoes], custos, talhao.area_ha, desde, ate)
    return TalhaoDetalhe(
        **dict(_resposta(talhao, aplicacoes, custos, hoje(), desde, ate)),
        aplicacoes=[MovimentacaoResposta.model_validate(m) for m in no_periodo],
        consumo=custo.consumo,
    )


def criar_talhao(db: Session, dados: TalhaoCadastro) -> TalhaoResposta:
    talhao = Talhao(**dados.model_dump())
    db.add(talhao)
    _salvar(db)
    return _resposta(talhao, [], {}, hoje())


def atualizar_talhao(db: Session, talhao_id: int, dados: TalhaoCadastro) -> TalhaoResposta:
    talhao = buscar_talhao(db, talhao_id)
    for campo, valor in dados.model_dump().items():
        setattr(talhao, campo, valor)
    _salvar(db)
    # A área mudou o custo por hectare; o nome, a frase da carência.
    aplicacoes = _aplicacoes(db, talhao_id).get(talhao_id, [])
    return _resposta(talhao, aplicacoes, _custos_medios(db), hoje())


def remover_talhao(db: Session, talhao_id: int) -> None:
    talhao = buscar_talhao(db, talhao_id)
    aplicacoes = db.scalar(
        select(func.count()).select_from(Movimentacao).where(Movimentacao.talhao_id == talhao_id)
    )
    if aplicacoes:
        raise TalhaoComAplicacoes(talhao.nome, aplicacoes)
    db.delete(talhao)
    try:
        db.commit()
    except IntegrityError as erro:
        # Uma aplicação lançada entre a contagem e o DELETE: o RESTRICT do banco barra.
        db.rollback()
        raise TalhaoComAplicacoes(talhao.nome, 1) from erro


def buscar_talhao(db: Session, talhao_id: int) -> Talhao:
    talhao = db.get(Talhao, talhao_id)
    if talhao is None:
        raise TalhaoInexistente
    return talhao


def _salvar(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        # A única restrição que a validação do schema não cobre é o nome único.
        raise NomeDuplicado from erro


type _Aplicacoes = list[tuple[Movimentacao, regras.Aplicacao]]


def _aplicacoes(db: Session, talhao_id: int | None = None) -> dict[int, _Aplicacoes]:
    """As retiradas lançadas em talhões, por talhão, com o insumo e a carência dele."""
    consulta = select(Movimentacao, Insumo).join(Insumo).where(Movimentacao.talhao_id.is_not(None))
    if talhao_id is not None:
        consulta = consulta.where(Movimentacao.talhao_id == talhao_id)
    por_talhao: dict[int, _Aplicacoes] = defaultdict(list)
    for movimentacao, insumo in db.execute(consulta):
        aplicacao = regras.Aplicacao(
            data=movimentacao.data,
            insumo_id=insumo.id,
            insumo=insumo.nome,
            unidade=insumo.unidade,
            quantidade=movimentacao.quantidade,
            carencia_dias=insumo.carencia_dias,
        )
        por_talhao[movimentacao.talhao_id].append((movimentacao, aplicacao))
    return por_talhao


def _custos_medios(db: Session) -> dict[int, float | None]:
    """O custo médio de cada insumo pela mesma regra da tela do insumo: o custo do talhão
    não pode discordar do valor em estoque."""
    entradas: dict[int, list[dominio.Entrada]] = defaultdict(list)
    compras = select(Movimentacao).where(
        Movimentacao.tipo == "entrada", Movimentacao.valor_unitario.is_not(None)
    )
    for m in db.scalars(compras):
        entradas[m.insumo_id].append(
            dominio.Entrada(m.data, m.quantidade, valor_unitario=m.valor_unitario)
        )
    return {insumo_id: dominio.custo_medio(lista) for insumo_id, lista in entradas.items()}


def _no_periodo(dia: date, desde: date | None, ate: date | None) -> bool:
    return (desde is None or dia >= desde) and (ate is None or dia <= ate)


def _resposta(
    talhao: Talhao,
    aplicacoes: _Aplicacoes,
    custos: dict[int, float | None],
    referencia: date,
    desde: date | None = None,
    ate: date | None = None,
) -> TalhaoResposta:
    do_dominio = [a for _, a in aplicacoes]
    # A carência olha todas as aplicações, seja qual for o período pedido: o recorte é do
    # custo, e um defensivo aplicado antes dele continua proibindo a colheita.
    carencia = regras.carencia(talhao.nome, do_dominio, referencia)
    custo = regras.custo(do_dominio, custos, talhao.area_ha, desde, ate)
    return TalhaoResposta(
        id=talhao.id,
        nome=talhao.nome,
        area_ha=talhao.area_ha,
        cultura=talhao.cultura,
        demonstracao=talhao.demonstracao,
        colheita_liberada_em=carencia.colheita_liberada_em,
        em_carencia=bool(carencia.alertas),
        alertas=carencia.alertas,
        custo_total=custo.total,
        custo_por_ha=custo.por_hectare,
        limitacoes=[*carencia.limitacoes, *custo.limitacoes],
    )
