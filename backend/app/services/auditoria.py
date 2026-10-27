"""A trilha de auditoria: gravar o evento de uma ação sensível ou destrutiva, e consultá-los.

Entra o que apaga, o que muda um cadastro de que outros dependem, o que mexe em quem
entra no sistema e as tentativas de entrar à força. Não entram a leitura nem o lançamento
comum: a movimentação já guarda quem a lançou (`usuario_id`), e um evento por lançamento
só repetiria isso. Pelo mesmo motivo, o recebimento de um pedido não entra: cada linha
recebida vira uma entrada com quem conferiu e o pedido dela (`item_do_pedido_id`).

O evento vai na transação de quem chama (`registrar` não faz commit): se a ação falha,
não há evento; se o evento falha, a ação não acontece.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal

from pydantic_core import to_jsonable_python
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.relogio import FUSO_RONDONIA
from app.models import EventoDeAuditoria, Movimentacao

# Os códigos são estáveis: a tela e os filtros dependem deles. Um novo entra aqui.
ACOES = (
    # O conteúdo inteiro do que foi apagado, para relançar à mão.
    "movimentacao.removida",
    "insumo.removido",  # com as movimentações e as linhas de pedido que foram junto
    "talhao.removido",
    "categoria.removida",
    "fornecedor.removido",
    # O antes e o depois do que mudou num cadastro de que outros dependem.
    "insumo.alterado",
    "talhao.alterado",
    "categoria.alterada",
    "fornecedor.alterado",
    "pedido.alterado",
    "pedido.cancelado",
    # O resumo do que entrou de uma vez.
    "importacao.confirmada",
    # Quem entra no sistema e com que poder.
    "usuario.criado",
    "usuario.alterado",
    "usuario.senha_redefinida",
    "usuario.senha_trocada",
    "login.recusado",
    "login.bloqueado",
    "login.limitado",  # um IP passou do limite de tentativas: uma vez por rodada
    # Um aparelho derrubado sem desativar ninguém (o celular perdido). Encerrar a sessão
    # que faz o pedido é sair, e não entra. Um grupo só, `sessao`, para o filtro.
    "sessao.encerrada",
    "sessao.encerradas",
    # A fazenda de demonstração, que apaga e cria em massa.
    "demo.carregada",
    "demo.limpa",
)

# Nunca num evento: quem lê a auditoria não pode sair com uma senha nem com um login aberto.
_SEGREDOS = {"senha", "senha_hash", "senha_atual", "senha_nova", "token", "token_hash"}


@dataclass(frozen=True)
class Origem:
    """Quem fez e de onde. `usuario_id` vazio: autenticação desligada, ou um comando no
    servidor (`canal="terminal"`)."""

    usuario_id: int | None = None
    ip: str | None = None
    dispositivo: str | None = None
    canal: Literal["api", "terminal"] = "api"


# A demonstração e o criar-dono, rodados no servidor: não há login nem endereço.
TERMINAL = Origem(canal="terminal")


def registrar(
    db: Session,
    origem: Origem,
    acao: str,
    entidade: str | None,
    entidade_id: int | None,
    dados: dict[str, Any],
) -> EventoDeAuditoria:
    """Põe o evento na sessão, sem commit: ele vai junto com a ação de quem chamou."""
    if acao not in ACOES:
        raise ValueError(f"ação de auditoria desconhecida: {acao}")
    if segredo := _segredo_em(dados):
        raise ValueError(f"segredo no evento de auditoria: {segredo}")
    evento = EventoDeAuditoria(
        usuario_id=origem.usuario_id,
        acao=acao,
        entidade=entidade,
        entidade_id=entidade_id,
        # Datas, uuids e números do jeito que o JSON aceita, no formato ISO.
        dados=to_jsonable_python(dados),
        origem=origem.canal,
        ip=origem.ip,
        dispositivo=origem.dispositivo,
    )
    db.add(evento)
    return evento


class AcaoDesconhecida(Exception):
    def __init__(self) -> None:
        grupos = ", ".join(sorted({acao.split(".")[0] for acao in ACOES}))
        super().__init__(
            "Ação desconhecida. Use o código de uma ação (como usuario.criado) ou o grupo "
            f"(como usuario): {grupos}."
        )


@dataclass(frozen=True)
class FiltroDeEventos:
    """Os recortes da consulta, todos opcionais e somados. `acao` é o código inteiro
    ("usuario.criado") ou o grupo ("usuario", ou "usuario."). `desde` e `ate` são dias de
    Rondônia, inclusive."""

    acao: str | None = None
    usuario_id: int | None = None
    entidade: str | None = None
    entidade_id: int | None = None
    desde: date | None = None
    ate: date | None = None


def listar(
    db: Session, filtro: FiltroDeEventos, limite: int, deslocamento: int = 0
) -> tuple[list[EventoDeAuditoria], int]:
    """Uma página dos eventos, os mais recentes primeiro, e quantos há com os mesmos
    filtros. O id desempata o mesmo instante, como na lista de movimentações."""
    e = EventoDeAuditoria
    condicoes = [
        coluna == valor
        for coluna, valor in (
            (e.usuario_id, filtro.usuario_id),
            (e.entidade, filtro.entidade),
            (e.entidade_id, filtro.entidade_id),
        )
        if valor is not None
    ]
    if filtro.acao is not None:
        # O grupo vira a lista dos códigos dele, e não um LIKE: o índice (acao, ...) serve
        # sem depender da collation, e o grupo que não existe é erro, e não lista vazia.
        condicoes.append(e.acao.in_(_acoes_do_filtro(filtro.acao)))
    # O dia é o de Rondônia (o do produtor), comparado em UTC, como o instante é gravado.
    if filtro.desde is not None:
        condicoes.append(e.ocorrido_em >= _inicio_do_dia(filtro.desde))
    if filtro.ate is not None:
        condicoes.append(e.ocorrido_em < _inicio_do_dia(filtro.ate + timedelta(days=1)))
    consulta = (
        select(e)
        .where(*condicoes)
        .order_by(e.ocorrido_em.desc(), e.id.desc())
        .limit(limite)
        .offset(deslocamento)
    )
    total = db.scalar(select(func.count()).select_from(e).where(*condicoes))
    return list(db.scalars(consulta)), total


def _acoes_do_filtro(acao: str) -> list[str]:
    grupo = acao.removesuffix(".")
    acoes = [a for a in ACOES if a == acao or a.split(".")[0] == grupo]
    if not acoes:
        raise AcaoDesconhecida
    return acoes


def _inicio_do_dia(dia: date) -> datetime:
    return datetime.combine(dia, time(), FUSO_RONDONIA).astimezone(UTC)


def diferencas(antes: dict[str, Any], depois: dict[str, Any]) -> dict[str, Any] | None:
    """O antes e o depois só dos campos que mudaram; None se nada mudou (e não há o que
    registrar)."""
    mudou = [campo for campo in depois if antes.get(campo) != depois[campo]]
    if not mudou:
        return None
    return {
        "antes": {campo: antes.get(campo) for campo in mudou},
        "depois": {campo: depois[campo] for campo in mudou},
    }


def retrato_da_movimentacao(m: Movimentacao, insumo: str, talhao: str | None) -> dict[str, Any]:
    """Tudo o que é preciso para relançar a movimentação à mão, com os nomes ao lado dos
    ids: o insumo, o talhão e o fornecedor podem não existir mais quando alguém ler."""
    return {
        "id": m.id,
        "insumo_id": m.insumo_id,
        "insumo": insumo,
        "tipo": m.tipo,
        "data": m.data,
        "quantidade": m.quantidade,
        "validade": m.validade,
        "motivo": m.motivo,
        "valor_unitario": m.valor_unitario,
        "talhao_id": m.talhao_id,
        "talhao": talhao,
        "fornecedor_id": m.fornecedor_id,
        "fornecedor": m.comprado_de,
        "uuid": m.uuid,
        "usuario_id": m.usuario_id,
        "lancado_por": m.lancado_por,
        "item_do_pedido_id": m.item_do_pedido_id,
    }


def _segredo_em(dados: object) -> str | None:
    if isinstance(dados, dict):
        for chave, valor in dados.items():
            if chave in _SEGREDOS:
                return chave
            if achado := _segredo_em(valor):
                return achado
    elif isinstance(dados, list | tuple):
        for valor in dados:
            if achado := _segredo_em(valor):
                return achado
    return None
