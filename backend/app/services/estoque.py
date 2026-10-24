"""Casos de uso do estoque: cadastro de insumos, movimentações e a análise de cada
insumo a partir do que está no banco."""

import unicodedata
from dataclasses import dataclass, replace
from datetime import date
from typing import Literal
from uuid import UUID

from sqlalchemy import ColumnElement, delete, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.analysis.consumo import analisar
from app.core.database import violou_nome_unico
from app.core.relogio import hoje
from app.domain import estoque as dominio
from app.models import (
    Categoria,
    Fornecedor,
    Insumo,
    ItemDoPedido,
    Movimentacao,
    Pedido,
    Talhao,
)
from app.schemas.estoque import (
    AjusteDeInventario,
    ContagemDeInventario,
    InsumoCadastro,
    InsumoDetalhe,
    InsumoResposta,
    MovimentacaoEntrada,
    MovimentacaoResposta,
    PontoDeEstoque,
    PrecoPago,
    como_o_banco,
)
from app.services import pedidos

# Campos que vieram depois do site e do app: um PUT que não os manda (de uma versão que
# não os conhece) mantém o que está gravado, em vez de apagá-los.
_CAMPOS_OPCIONAIS_NOVOS = {"embalagem", "pedido_minimo", "carencia_dias", "categoria_id"}
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
    "talhao_id": None,
    "fornecedor_id": None,
}


class NomeDuplicado(Exception):
    pass


class InsumoInexistente(Exception):
    pass


class TalhaoInexistente(Exception):
    pass


class FornecedorInexistente(Exception):
    pass


class CategoriaInexistente(Exception):
    pass


class InsumoAplicadoEmTalhao(Exception):
    """Remover o insumo levaria as aplicações junto (CASCADE), e o talhão sairia da
    carência calado. Mesma regra que impede remover talhão com aplicação."""

    def __init__(self, nome: str, talhoes: list[str]) -> None:
        super().__init__(
            f'"{nome}" foi aplicado em {", ".join(talhoes)}: removê-lo apagaria onde foi '
            "aplicado e a carência do talhão. Se foi lançado por engano, remova antes as "
            "aplicações dele."
        )


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


def listar_insumos(
    db: Session,
    categoria_id: int | None = None,
    busca: str | None = None,
    gravidade: Literal["alta", "media", "baixa"] | None = None,
    com_alerta: bool | None = None,
) -> list[InsumoResposta]:
    """Todos, pelo nome; os filtros são opcionais e se somam. O alerta só existe depois da
    análise, então `gravidade` e `com_alerta` filtram a lista já analisada (a análise de
    cada insumo lê todas as movimentações dele de qualquer jeito)."""
    consulta = select(Insumo).options(selectinload(Insumo.movimentacoes)).order_by(Insumo.nome)
    if categoria_id is not None:
        consulta = consulta.where(Insumo.categoria_id == categoria_id)
    if busca is not None:
        consulta = consulta.where(Insumo.id.in_(ids_pelo_nome(db, busca)))
    referencia = hoje()
    pedidos = a_caminho(db)
    respostas = [
        _resposta(insumo, referencia, pedidos.get(insumo.id, [])) for insumo in db.scalars(consulta)
    ]
    if gravidade is not None:
        respostas = [
            r for r in respostas if any(a.gravidade == gravidade for a in r.analise.alertas)
        ]
    if com_alerta is not None:
        respostas = [r for r in respostas if bool(r.analise.alertas) == com_alerta]
    return respostas


def ids_pelo_nome(db: Session, busca: str) -> list[int]:
    """Os insumos cujo nome contém `busca`, sem diferenciar maiúsculas nem acentos ("ureia"
    acha "Uréia"). A comparação é feita aqui, e não no banco: o PostgreSQL só ignora acento
    com a extensão `unaccent`, que o SQLite dos testes não tem, e o `lower()` do SQLite só
    conhece as letras sem acento ("É" ficaria "É"). Feita em Python, dá o mesmo resultado
    nos dois. Os insumos de uma fazenda são centenas, e ler só id e nome custa pouco."""
    procurado = _como_se_busca(busca)
    return [
        insumo_id
        for insumo_id, nome in db.execute(select(Insumo.id, Insumo.nome))
        if procurado in _como_se_busca(nome)
    ]


def _como_se_busca(texto: str) -> str:
    # NFKD separa a letra do acento ("é" vira "e" + acento), e o acento sai; casefold é o
    # lower() que também iguala letras como o "ß".
    decomposto = unicodedata.normalize("NFKD", texto.strip())
    return "".join(c for c in decomposto if not unicodedata.combining(c)).casefold()


def criar_insumo(db: Session, dados: InsumoCadastro) -> InsumoResposta:
    _conferir_categoria(db, dados.categoria_id)
    insumo = Insumo(**dados.model_dump())
    db.add(insumo)
    _salvar(db)
    _recarregar_categoria(db, insumo)
    return _resposta(insumo, hoje())


def atualizar_insumo(db: Session, insumo_id: int, dados: InsumoCadastro) -> InsumoResposta:
    insumo = _buscar_insumo(db, insumo_id)
    _conferir_categoria(db, dados.categoria_id)
    for campo, valor in dados.model_dump().items():
        if campo in _CAMPOS_OPCIONAIS_NOVOS and campo not in dados.model_fields_set:
            continue
        setattr(insumo, campo, valor)
    _salvar(db)
    _recarregar_categoria(db, insumo)
    return _resposta(insumo, hoje(), a_caminho(db, insumo_id).get(insumo_id, []))


def a_caminho(db: Session, insumo_id: int | None = None) -> dict[int, list[dominio.Encomenda]]:
    """O que foi pedido e não chegou, por insumo: a parte que falta de cada linha dos
    pedidos abertos ou parciais. O cancelado não vem mais, e o que veio a mais não conta."""
    consulta = (
        select(ItemDoPedido, Pedido.previsto_para)
        .join(Pedido)
        .where(Pedido.situacao.in_(("aberto", "parcial")))
    )
    if insumo_id is not None:
        consulta = consulta.where(ItemDoPedido.insumo_id == insumo_id)
    por_insumo: dict[int, list[dominio.Encomenda]] = {}
    for item, previsto_para in db.execute(consulta):
        if item.falta_receber > 0:
            encomenda = dominio.Encomenda(item.falta_receber, previsto_para)
            por_insumo.setdefault(item.insumo_id, []).append(encomenda)
    return por_insumo


def detalhar_insumo(db: Session, insumo_id: int) -> InsumoDetalhe:
    insumo = _buscar_insumo(db, insumo_id)
    movimentacoes = sorted(insumo.movimentacoes, key=lambda m: (m.data, m.id))
    saldo, por_dia = 0.0, {}
    for m in movimentacoes:
        saldo += m.quantidade if m.tipo == "entrada" else -m.quantidade
        # Vários lançamentos no mesmo dia: vale o saldo depois do último.
        por_dia[m.data] = round(saldo, 3)
    return InsumoDetalhe(
        **dict(_resposta(insumo, hoje(), a_caminho(db, insumo_id).get(insumo_id, []))),
        historico=[PontoDeEstoque(data=dia, saldo=valor) for dia, valor in por_dia.items()],
        movimentacoes=[MovimentacaoResposta.model_validate(m) for m in reversed(movimentacoes)],
        precos_por_fornecedor=sorted(
            precos_pagos([(m, insumo) for m in movimentacoes]),
            # O mais barato primeiro; quem não tem preço vai para o fim.
            key=lambda p: (p.preco_medio is None, p.preco_medio or 0, p.fornecedor),
        ),
    )


def precos_pagos(compras: list[tuple[Movimentacao, Insumo]]) -> list[PrecoPago]:
    """O que se pagou a cada fornecedor por cada insumo, na ordem em que aparecem. Só as
    compras com fornecedor; o preço médio pela mesma regra do custo médio."""
    grupos: dict[tuple[int, int], list[Movimentacao]] = {}
    insumos: dict[int, Insumo] = {}
    for m, insumo in compras:
        if m.fornecedor_id is not None and m.tipo == "entrada" and m.motivo is None:
            grupos.setdefault((insumo.id, m.fornecedor_id), []).append(m)
            insumos[insumo.id] = insumo
    precos = []
    for (insumo_id, fornecedor_id), grupo in grupos.items():
        movimentacoes = sorted(grupo, key=lambda m: (m.data, m.id))
        insumo = insumos[insumo_id]
        com_preco = [m for m in movimentacoes if m.valor_unitario is not None]
        precos.append(
            PrecoPago(
                insumo_id=insumo_id,
                insumo=insumo.nome,
                unidade=insumo.unidade,
                fornecedor_id=fornecedor_id,
                fornecedor=movimentacoes[0].comprado_de,
                compras=len(movimentacoes),
                quantidade=round(sum(m.quantidade for m in movimentacoes), 3),
                preco_medio=dominio.custo_medio(
                    dominio.Entrada(m.data, m.quantidade, valor_unitario=m.valor_unitario)
                    for m in com_preco
                ),
                ultimo_preco=com_preco[-1].valor_unitario if com_preco else None,
                ultima_compra=movimentacoes[-1].data,
            )
        )
    return precos


def remover_insumo(db: Session, insumo_id: int) -> None:
    insumo = _buscar_insumo(db, insumo_id)
    talhoes = db.scalars(
        select(Talhao.nome)
        .join(Movimentacao, Movimentacao.talhao_id == Talhao.id)
        .where(Movimentacao.insumo_id == insumo_id)
        .distinct()
        .order_by(Talhao.nome)
    ).all()
    if talhoes:
        raise InsumoAplicadoEmTalhao(insumo.nome, list(talhoes))
    # As outras movimentações vão junto pelo ON DELETE CASCADE, e as linhas de pedido dele
    # também. O pedido que fica sem linha nenhuma não diz mais nada: sai junto.
    db.delete(insumo)
    db.flush()
    db.execute(
        delete(Pedido).where(~exists().where(ItemDoPedido.pedido_id == Pedido.id)),
        execution_options={"synchronize_session": False},
    )
    db.commit()


@dataclass(frozen=True)
class FiltroDeMovimentacoes:
    """Os recortes da lista de movimentações, todos opcionais e somados. `motivo="nenhum"`
    é a movimentação sem motivo: a retirada para uso, na saída, e a compra, na entrada."""

    insumo_id: int | None = None
    tipo: Literal["entrada", "saida"] | None = None
    motivo: Literal["descarte", "inventario", "nenhum"] | None = None
    categoria_id: int | None = None
    talhao_id: int | None = None
    fornecedor_id: int | None = None
    usuario_id: int | None = None
    desde: date | None = None  # inclusive
    ate: date | None = None  # inclusive
    busca: str | None = None  # no nome do insumo, como em GET /insumos


def listar_movimentacoes(
    db: Session, filtro: FiltroDeMovimentacoes, limite: int, deslocamento: int = 0
) -> tuple[list[Movimentacao], int]:
    """Uma página das movimentações, as mais recentes primeiro, e quantas há ao todo com os
    mesmos filtros. O id desempata o mesmo dia: sem ele, duas do mesmo dia podiam trocar de
    lugar entre um pedido e outro, e uma página repetiria a que a anterior já mostrou."""
    condicoes = condicoes_do_filtro(db, filtro)
    consulta = (
        select(Movimentacao)
        .where(*condicoes)
        .order_by(Movimentacao.data.desc(), Movimentacao.id.desc())
        .limit(limite)
        .offset(deslocamento)
    )
    total = db.scalar(select(func.count()).select_from(Movimentacao).where(*condicoes))
    return list(db.scalars(consulta)), total


def condicoes_do_filtro(db: Session, filtro: FiltroDeMovimentacoes) -> list[ColumnElement[bool]]:
    m = Movimentacao
    condicoes = [
        coluna == valor
        for coluna, valor in (
            (m.insumo_id, filtro.insumo_id),
            (m.tipo, filtro.tipo),
            (m.talhao_id, filtro.talhao_id),
            (m.fornecedor_id, filtro.fornecedor_id),
            (m.usuario_id, filtro.usuario_id),
        )
        if valor is not None
    ]
    if filtro.motivo == "nenhum":
        condicoes.append(m.motivo.is_(None))
    elif filtro.motivo is not None:
        condicoes.append(m.motivo == filtro.motivo)
    if filtro.desde is not None:
        condicoes.append(m.data >= filtro.desde)
    if filtro.ate is not None:
        condicoes.append(m.data <= filtro.ate)
    if filtro.categoria_id is not None:
        # Subconsulta, e não join: a contagem e a página continuam uma linha por movimentação.
        da_categoria = select(Insumo.id).where(Insumo.categoria_id == filtro.categoria_id)
        condicoes.append(m.insumo_id.in_(da_categoria))
    if filtro.busca is not None:
        condicoes.append(m.insumo_id.in_(ids_pelo_nome(db, filtro.busca)))
    return condicoes


def registrar_movimentacao(
    db: Session, dados: MovimentacaoEntrada, usuario_id: int | None = None
) -> Registro:
    """Grava o lançamento em nome de `usuario_id`. Com `uuid` já gravado, é o app reenviando
    (a resposta anterior se perdeu no caminho): devolve o que está no banco, sem gravar de
    novo, e com o autor de antes."""
    _buscar_insumo(db, dados.insumo_id)
    if dados.talhao_id is not None and db.get(Talhao, dados.talhao_id) is None:
        raise TalhaoInexistente
    # Desativado vale: desativar tira das escolhas novas, e a compra pode ser antiga.
    if dados.fornecedor_id is not None and db.get(Fornecedor, dados.fornecedor_id) is None:
        raise FornecedorInexistente
    if dados.uuid is not None and (existente := _pelo_uuid(db, dados.uuid)) is not None:
        return _reenvio(existente, dados)
    movimentacao = Movimentacao(**dados.model_dump(), usuario_id=usuario_id)
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
    db: Session, insumo_id: int, contagem: ContagemDeInventario, usuario_id: int | None = None
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
            usuario_id=usuario_id,
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
    if movimentacao.item_do_pedido_id is not None:
        # A entrada recebeu parte de um pedido: removida (digitada errado), essa parte volta
        # a faltar, e o pedido volta a parcial ou aberto. Na mesma transação.
        # Trava o pedido antes de ler a linha, na mesma ordem do recebimento: os dois ao
        # mesmo tempo entram um de cada vez, sem se travar um ao outro.
        item = db.get(ItemDoPedido, movimentacao.item_do_pedido_id)
        pedido = pedidos.buscar_pedido(db, item.pedido_id, travar=True)
        db.refresh(item)
        item.quantidade_recebida = max(
            round(item.quantidade_recebida - movimentacao.quantidade, 3), 0
        )
        pedido.situacao = pedidos.situacao_pelo_recebido(pedido)
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
    # Como o PostgreSQL arredonda, e não o round() do Python: senão o reenvio idêntico de
    # 1,2345 kg compararia 1,234 com o 1,235 gravado e viraria "lançamento diferente".
    return como_o_banco(valor, casas) if casas is not None and isinstance(valor, float) else valor


def _buscar_insumo(db: Session, insumo_id: int) -> Insumo:
    insumo = db.get(Insumo, insumo_id)
    if insumo is None:
        raise InsumoInexistente
    return insumo


def _conferir_categoria(db: Session, categoria_id: int | None) -> None:
    if categoria_id is not None and db.get(Categoria, categoria_id) is None:
        raise CategoriaInexistente


def _recarregar_categoria(db: Session, insumo: Insumo) -> None:
    # A sessão não expira o que foi gravado (expire_on_commit=False): sem isto, a resposta
    # diria o nome da categoria de antes da troca.
    db.refresh(insumo, ["categoria"])


def _salvar(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        # Só o nome único vira "já existe": outra regra violada é defeito, não do usuário,
        # e dizer "nome repetido" mandaria o produtor procurar o problema no lugar errado.
        if violou_nome_unico(erro, "insumos"):
            raise NomeDuplicado from erro
        raise


def _resposta(
    insumo: Insumo, referencia: date, pedidos: list[dominio.Encomenda] = ()
) -> InsumoResposta:
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
        a_caminho=pedidos,
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
        carencia_dias=insumo.carencia_dias,
        categoria_id=insumo.categoria_id,
        categoria=None if insumo.categoria is None else insumo.categoria.nome,
        estoque_atual=estoque,
        custo_medio=None if custo_medio is None else round(custo_medio, 4),
        # Estoque negativo é registro faltando, não dívida: vale zero.
        valor_em_estoque=None if custo_medio is None else round(max(estoque, 0) * custo_medio, 2),
        em_pedido=round(sum(e.quantidade for e in pedidos), 3),
        chegada_prevista=max(
            (e.previsto_para for e in pedidos if e.previsto_para is not None), default=None
        ),
        analise=analise,
    )
