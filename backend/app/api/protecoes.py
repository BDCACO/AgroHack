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
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger_de_acesso = logging.getLogger("app.acesso")

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
    """Dá um id a cada pedido (`X-Request-ID`) e escreve uma linha de log por pedido.

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
        status = 500

        async def enviar(mensagem: Message) -> None:
            nonlocal status
            if mensagem["type"] == "http.response.start":
                status = mensagem["status"]
                MutableHeaders(scope=mensagem)["X-Request-ID"] = id_
            await send(mensagem)

        try:
            await self.app(scope, receive, enviar)
        finally:
            cliente = scope.get("client")
            linha = {
                "id": id_,
                "metodo": scope["method"],
                "caminho": scope["path"],
                "status": status,
                "duracao_ms": round((time.perf_counter() - inicio) * 1000, 1),
                "usuario_id": estado.get("usuario_id"),
                "ip": cliente[0] if cliente else None,
            }
            logger_de_acesso.info(json.dumps(linha, ensure_ascii=False))


def _id_aceito(enviado: str | None) -> str | None:
    if enviado is not None and _ID_SEGURO.fullmatch(enviado):
        return enviado
    return None
