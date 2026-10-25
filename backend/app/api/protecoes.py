"""As proteções que valem para todo pedido, como middlewares ASGI puros (e não o
`@app.middleware("http")` do Starlette, que não deixa embrulhar o `receive`).

A ordem, de fora para dentro, está em `app/main.py`.
"""

import json
import logging
import re
import time
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger_de_acesso = logging.getLogger("app.acesso")
logger_de_erros = logging.getLogger("app.erro")

# O 500 não conta o defeito a quem pediu (o traceback mostra código, consultas e às vezes
# dados): diz o que fazer e dá o código para achar o traceback no log.
FRASE_DO_ERRO_INESPERADO = (
    "Algo deu errado no servidor. Tente de novo; se continuar, informe ao suporte o código "
    "do pedido."
)

# O id que o cliente manda só é aceito se for seguro de escrever num log e num cabeçalho:
# letras sem acento, números, hífen e sublinhado, até 64 (um UUID cabe). Qualquer outra
# coisa (espaço, quebra de linha, acento) poderia forjar linhas no log; vira um id novo.
_ID_SEGURO = re.compile(r"[A-Za-z0-9_-]{1,64}")


def id_da_requisicao(request: Request) -> str | None:
    """O id deste pedido, o mesmo do cabeçalho `X-Request-ID` e da linha do log."""
    return getattr(request.state, "id_da_requisicao", None)


def anotar_o_usuario(request: Request, usuario_id: int) -> None:
    """Quem fez o pedido, para a linha do log de acesso (as permissões o descobrem)."""
    request.state.usuario_id = usuario_id


class RegistroDosPedidos:
    """Dá um id a cada pedido (`X-Request-ID`), escreve uma linha de log por pedido e
    transforma o erro inesperado em 500 com frase e id (o traceback vai só para o log).

    A linha é JSON, para se filtrar no log sem expressão regular: id, método, caminho (sem a
    query string, que pode trazer o que se buscou), status, duração em ms, usuário e IP.
    Nunca o corpo nem os cabeçalhos: é onde andam a senha e o token."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        id_ = _id_aceito(Headers(scope=scope).get("x-request-id")) or str(uuid4())
        estado = scope.setdefault("state", {})
        estado["id_da_requisicao"] = id_
        inicio = time.perf_counter()
        status_enviado: int | None = None

        async def enviar(mensagem: Message) -> None:
            nonlocal status_enviado
            if mensagem["type"] == "http.response.start":
                status_enviado = mensagem["status"]
                MutableHeaders(scope=mensagem)["X-Request-ID"] = id_
            await send(mensagem)

        try:
            await self.app(scope, receive, enviar)
        except Exception:
            # Aqui, e não num exception_handler: o do Starlette para `Exception` roda fora de
            # todos os middlewares, e a resposta sairia sem o id e sem os cabeçalhos de
            # segurança. Engolido depois de logado: o servidor não loga o mesmo traceback
            # de novo.
            logger_de_erros.exception(
                "Erro inesperado no pedido %s (%s %s).", id_, scope["method"], scope["path"]
            )
            if status_enviado is None:
                resposta = JSONResponse(
                    {"detail": FRASE_DO_ERRO_INESPERADO, "id_da_requisicao": id_},
                    status_code=500,
                )
                await resposta(scope, receive, enviar)
        finally:
            cliente = scope.get("client")
            linha = {
                "id": id_,
                "metodo": scope["method"],
                "caminho": scope["path"],
                # Sem resposta: o erro veio depois de ela começar, ou o cliente se foi.
                "status": status_enviado or 500,
                "duracao_ms": round((time.perf_counter() - inicio) * 1000, 1),
                "usuario_id": estado.get("usuario_id"),
                "ip": cliente[0] if cliente else None,
            }
            logger_de_acesso.info(json.dumps(linha, ensure_ascii=False))


def _id_aceito(enviado: str | None) -> str | None:
    if enviado is not None and _ID_SEGURO.fullmatch(enviado):
        return enviado
    return None


FRASE_DO_CORPO_GRANDE = "Arquivo grande demais: o máximo é 5 MB."


class LimiteDoCorpo:
    """Recusa com 413 o pedido cujo corpo passa de `maximo` bytes, contando os bytes que
    chegam, e não só o `Content-Length`: o pedido `Transfer-Encoding: chunked` não o traz e,
    sem a conta, iria inteiro para a memória (o FastAPI lê o corpo todo antes de validar).

    O `Content-Length` acima do limite é recusado antes de ler um byte. Sem ele, o `receive`
    embrulhado soma o que chega; ao passar do limite, responde 413 dali mesmo e diz à API
    que o cliente se foi (`http.disconnect`): ela para de ler, e o que tentar responder
    depois é descartado. O uvicorn fecha a conexão com o resto do corpo sem ler."""

    def __init__(self, app: ASGIApp, maximo: int) -> None:
        self.app = app
        self.maximo = maximo

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        tamanho = Headers(scope=scope).get("content-length", "")
        if tamanho.isdigit() and int(tamanho) > self.maximo:
            await _corpo_grande_demais(scope, send)
            return
        recebidos = 0
        estourou = False
        respondeu = False

        async def receber() -> Message:
            nonlocal recebidos, estourou
            if estourou:
                return {"type": "http.disconnect"}
            mensagem = await receive()
            if mensagem["type"] == "http.request":
                recebidos += len(mensagem.get("body", b""))
                if recebidos > self.maximo:
                    estourou = True
                    if not respondeu:
                        await _corpo_grande_demais(scope, send)
                    return {"type": "http.disconnect"}
            return mensagem

        async def enviar(mensagem: Message) -> None:
            nonlocal respondeu
            if estourou:
                return  # o 413 já foi; a resposta da API ao "cliente que se foi" não vai
            if mensagem["type"] == "http.response.start":
                respondeu = True
            await send(mensagem)

        await self.app(scope, receber, enviar)


async def _corpo_grande_demais(scope: Scope, send: Send) -> None:
    resposta = JSONResponse({"detail": FRASE_DO_CORPO_GRANDE}, status_code=413)
    await resposta(scope, _nada_a_receber, send)


async def _nada_a_receber() -> Message:
    return {"type": "http.disconnect"}
