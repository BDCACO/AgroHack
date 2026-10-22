"""Sincronização do app: a fila de lançamentos feitos no campo, sem sinal, enviada de uma
vez quando a rede volta.

Item a item, e não tudo ou nada como a importação de planilha: a fila é do celular, e um
item ruim não pode travar os outros, que o produtor já fez e não vai refazer. Cada item é
gravado na própria transação; se o envio cair no meio, o app manda o lote de novo, e o
que já entrou volta como `ja_existia`, pelo uuid.
"""

from typing import Any
from uuid import UUID

from pydantic import ValidationError
from pydantic_core import ErrorDetails
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.relogio import hoje
from app.domain.estoque import quantidade_legivel
from app.models import Insumo, Movimentacao
from app.schemas.estoque import (
    MovimentacaoDoLote,
    MovimentacaoResposta,
    ResultadoDoItem,
    ResultadoDoLote,
    ResumoDoLote,
)
from app.services import estoque

# Lançamento com data mais antiga que isto provavelmente tem o ano ou o mês digitado errado
# (ou ficou esquecido na fila): a API grava, mas pede para conferir.
DIAS_DE_ATRASO = 30


def sincronizar(db: Session, itens: list[Any]) -> ResultadoDoLote:
    resultados = [_sincronizar_item(db, item) for item in itens]
    _avisar(db, resultados)
    situacoes = [r.situacao for r in resultados]
    return ResultadoDoLote(
        resultados=resultados,
        resumo=ResumoDoLote(
            gravadas=situacoes.count("gravada"),
            ja_existiam=situacoes.count("ja_existia"),
            recusadas=situacoes.count("recusada"),
        ),
    )


def _sincronizar_item(db: Session, item: Any) -> ResultadoDoItem:
    try:
        dados = MovimentacaoDoLote.model_validate(item)
    except ValidationError as erro:
        return ResultadoDoItem(uuid=_uuid_legivel(item), situacao="recusada", erros=_frases(erro))
    try:
        registro = estoque.registrar_movimentacao(db, dados)
    except estoque.InsumoInexistente:
        erro = f"O insumo {dados.insumo_id} não existe: pode ter sido removido no site."
        return ResultadoDoItem(uuid=dados.uuid, situacao="recusada", erros=[erro])
    except estoque.LancamentoDiferente as erro:
        return ResultadoDoItem(uuid=dados.uuid, situacao="recusada", erros=[str(erro)])
    return ResultadoDoItem(
        uuid=dados.uuid,
        situacao="gravada" if registro.nova else "ja_existia",
        movimentacao=MovimentacaoResposta.model_validate(registro.movimentacao),
    )


def _avisar(db: Session, resultados: list[ResultadoDoItem]) -> None:
    """Avisos não impedem nada: pedem ao produtor que confira. Calculados depois do lote
    inteiro, e também para o que `ja_existia`: a resposta do primeiro envio pode ter se
    perdido, e o aviso com ela."""
    aceitos = [r for r in resultados if r.movimentacao is not None]
    # O estoque que importa é o do fim do lote: a fila segue a ordem em que o produtor
    # lançou, e uma entrada mais adiante pode cobrir a saída. Uma vez por insumo, na
    # última saída dele.
    ultima_saida = {r.movimentacao.insumo_id: r for r in aceitos if r.movimentacao.tipo == "saida"}
    for insumo_id, resultado in ultima_saida.items():
        insumo = db.get(Insumo, insumo_id)
        saldo = _saldo(db, insumo_id)
        if insumo is not None and saldo < 0:
            resultado.avisos.append(
                f"O estoque de {insumo.nome} fica em {quantidade_legivel(saldo, insumo.unidade)} "
                "com este envio: falta lançar uma entrada?"
            )
    for resultado in aceitos:
        movimentacao = resultado.movimentacao
        atraso = (hoje() - movimentacao.data).days
        if atraso > DIAS_DE_ATRASO:
            resultado.avisos.append(
                f"Lançamento atrasado: a data é {movimentacao.data:%d/%m/%Y}, {atraso} dias "
                "atrás. Confira a data."
            )
        if _igual_sem_uuid(db, movimentacao):
            resultado.avisos.append(
                "Já existe um lançamento igual neste dia, feito sem o app (no site ou pela "
                "planilha). Se for o mesmo, remova um dos dois."
            )


def _saldo(db: Session, insumo_id: int) -> float:
    sinal = case((Movimentacao.tipo == "entrada", 1), else_=-1)
    total = db.scalar(
        select(func.sum(sinal * Movimentacao.quantidade)).where(Movimentacao.insumo_id == insumo_id)
    )
    # Tira o resíduo do float, como o estoque da análise.
    return round(total or 0, 3)


def _igual_sem_uuid(db: Session, movimentacao: MovimentacaoResposta) -> bool:
    """O mesmo lançamento digitado no site e no app: o uuid não ajuda (o do site não tem),
    então só o conteúdo denuncia. Duas retiradas iguais no mesmo dia existem de verdade,
    por isso é aviso, não recusa."""
    consulta = select(Movimentacao.id).where(
        Movimentacao.uuid.is_(None),
        Movimentacao.insumo_id == movimentacao.insumo_id,
        Movimentacao.tipo == movimentacao.tipo,
        Movimentacao.data == movimentacao.data,
        Movimentacao.quantidade == movimentacao.quantidade,
        Movimentacao.validade.is_not_distinct_from(movimentacao.validade),
        Movimentacao.motivo.is_not_distinct_from(movimentacao.motivo),
        Movimentacao.valor_unitario.is_not_distinct_from(movimentacao.valor_unitario),
    )
    return db.scalar(consulta.limit(1)) is not None


def _uuid_legivel(item: Any) -> UUID | None:
    try:
        return UUID(str(item["uuid"]))
    except TypeError, KeyError, ValueError:
        return None


def _frases(erro: ValidationError) -> list[str]:
    """Os erros do Pydantic (em inglês, para programador) viram frases para a tela do app,
    com o nome do campo, como o produtor vai ver ao lado do lançamento recusado."""
    return [_frase(detalhe) for detalhe in erro.errors(include_url=False)]


def _frase(detalhe: ErrorDetails) -> str:
    campo = ".".join(str(parte) for parte in detalhe["loc"])
    tipo = detalhe["type"]
    contexto = detalhe.get("ctx", {})
    if tipo in {"model_type", "model_attributes_type"}:
        return (
            "O item não é um lançamento: mande um objeto com uuid, insumo_id, tipo, data e "
            "quantidade."
        )
    if tipo == "missing":
        if campo == "uuid":
            return "Falta o campo uuid, que o app gera para cada lançamento."
        return f"Falta o campo {campo}."
    if tipo == "value_error":
        # As regras do schema (data futura, validade em saída...) já são frases em português.
        texto = str(contexto["error"])
        return f"{texto[:1].upper()}{texto[1:]}."
    if tipo == "greater_than":
        return f"{campo} tem de ser maior que {_limite(contexto['gt'])}."
    if tipo == "less_than_equal":
        return f"{campo} passa do máximo aceito ({_limite(contexto['le'])})."
    if tipo == "literal_error":
        return f"{campo} tem de ser {str(contexto['expected']).replace(' or ', ' ou ')}."
    if tipo.startswith(("date_", "datetime_")):
        return f"{campo} não é uma data válida: use AAAA-MM-DD."
    if tipo.startswith("uuid_"):
        return f"{campo} não é um identificador válido: gere um UUID v4 para cada lançamento."
    if tipo.startswith("int_"):
        return f"{campo} tem de ser um número inteiro."
    if tipo.startswith("float_") or tipo == "finite_number":
        return f"{campo} tem de ser um número."
    return f"{campo or 'O lançamento'} está inválido."


def _limite(valor: float) -> str:
    """0.0 → "0"; 999999999 → "999.999.999": o número como o produtor escreve."""
    return f"{valor:,.3f}".rstrip("0").rstrip(".").translate(str.maketrans(",.", ".,"))
