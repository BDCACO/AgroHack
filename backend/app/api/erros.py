"""Tradução de erro de negócio para HTTP — o único lugar que conhece os dois lados."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.domain import erros
from app.schemas.comum import Erro

_STATUS: dict[type[erros.ErroDeNegocio], int] = {
    erros.InsumoNaoEncontrado: status.HTTP_404_NOT_FOUND,
    erros.MovimentacaoNaoEncontrada: status.HTTP_404_NOT_FOUND,
    erros.InsumoDuplicado: status.HTTP_409_CONFLICT,
    erros.InsumoComMovimentacoes: status.HTTP_409_CONFLICT,
    erros.EstoqueInsuficiente: status.HTTP_409_CONFLICT,
}

# Para declarar nas rotas: `responses=RESPOSTAS_DE_ERRO`, e o OpenAPI documenta o corpo.
RESPOSTAS_DE_ERRO: dict[int | str, dict[str, object]] = {
    codigo: {"model": Erro} for codigo in sorted(set(_STATUS.values()))
}


async def _tratar(_: Request, erro: erros.ErroDeNegocio) -> JSONResponse:
    corpo = Erro(codigo=erro.codigo, mensagem=erro.mensagem)
    # Erro sem mapeamento é bug de quem criou o erro: 422 é o status menos errado.
    codigo_http = _STATUS.get(type(erro), status.HTTP_422_UNPROCESSABLE_CONTENT)
    return JSONResponse(corpo.model_dump(), status_code=codigo_http)


def registrar_tratadores(app: FastAPI) -> None:
    app.add_exception_handler(erros.ErroDeNegocio, _tratar)  # type: ignore[arg-type]
