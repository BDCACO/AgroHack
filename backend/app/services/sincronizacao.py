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
from sqlalchemy.orm import Session

from app.schemas.estoque import (
    MovimentacaoDoLote,
    MovimentacaoResposta,
    ResultadoDoItem,
    ResultadoDoLote,
    ResumoDoLote,
)
from app.services import estoque


def sincronizar(db: Session, itens: list[Any]) -> ResultadoDoLote:
    resultados = [_sincronizar_item(db, item) for item in itens]
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
