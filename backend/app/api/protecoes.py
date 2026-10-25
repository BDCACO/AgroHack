"""As proteções que valem para todo pedido, como middlewares ASGI puros (e não o
`@app.middleware("http")` do Starlette, que não deixa embrulhar o `receive`).

A ordem, de fora para dentro, está em `app/main.py`.
"""

import base64
import hashlib
import ipaddress
import json
import logging
import math
import re
import time
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.limite_de_taxa import LimiteDeTaxa

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


def ip_do_cliente(scope: Scope) -> str | None:
    """O IP de quem fez o pedido, como o uvicorn o viu (`client`): o mesmo nos limites por
    IP, na trilha, na sessão e no log. O `X-Forwarded-For` não é lido aqui, e o uvicorn sobe
    com `--no-proxy-headers` para não trocar o `client` pelo texto dele (ver "Qual IP" em
    docs/ARQUITETURA.md).

    Só um IP de verdade passa, na forma canônica. Se um dia o uvicorn subir sem a opção, o
    que alguém escreveu no cabeçalho ("evil", uma quebra de linha, 300 letras) não chega à
    trilha nem às colunas de 45 letras (seria um 500 no login), e todos esses textos caem na
    mesma conta dos limites, em vez de cada um abrir uma nova. Um IP forjado ainda passaria:
    contra ele, só a opção do uvicorn."""
    cliente = scope.get("client")
    if not cliente:
        return None
    try:
        return str(ipaddress.ip_address(cliente[0]))
    except ValueError:
        return None


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
            linha = {
                "id": id_,
                "metodo": scope["method"],
                "caminho": scope["path"],
                # Sem resposta: o erro veio depois de ela começar, ou o cliente se foi.
                "status": status_enviado or 500,
                "duracao_ms": round((time.perf_counter() - inicio) * 1000, 1),
                "usuario_id": estado.get("usuario_id"),
                "ip": ip_do_cliente(scope),
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


_GRAVAM = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def frase_de_espera(inicio: str, espere: int) -> str:
    """'<inicio>. Espere N minutos e tente de novo.', com os minutos para cima: o produtor
    lê minutos, e o Retry-After leva os segundos exatos para o app."""
    minutos = math.ceil(espere / 60)
    return f"{inicio}. Espere {minutos} minuto{'s' if minutos > 1 else ''} e tente de novo."


def muitos_pedidos(frase: str, espere: int) -> JSONResponse:
    return JSONResponse({"detail": frase}, status_code=429, headers={"Retry-After": str(espere)})


class LimiteDeEscritas:
    """Limita os pedidos que gravam por IP (`limite`), com 429 e `Retry-After` antes de a API
    ler o corpo. Leitura não conta (o Painel recarrega tudo a cada alteração), nem o login,
    que tem o limite dele (app/api/routes/autenticacao.py) e não pode gastar o das escritas.

    O IP é o que o uvicorn vê (`ip_do_cliente`), como na auditoria; o `X-Forwarded-For`
    qualquer um escreve, e trocá-lo a cada pedido zeraria a conta. Sem evento de auditoria: não é
    tentativa de entrar à força, e cada 429 seria uma linha."""

    def __init__(self, app: ASGIApp, limite: LimiteDeTaxa, isentos: frozenset[str]) -> None:
        self.app = app
        self.limite = limite
        self.isentos = isentos

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and scope["method"] in _GRAVAM
            and scope["path"] not in self.isentos
        ):
            recusa = self.limite.tentar(ip_do_cliente(scope) or "desconhecido")
            if recusa is not None:
                frase = frase_de_espera(
                    "Muitos pedidos seguidos a partir desta rede", recusa.espere
                )
                await muitos_pedidos(frase, recusa.espere)(scope, _nada_a_receber, send)
                return
        await self.app(scope, receive, send)


# Em toda resposta da API. Nenhuma é página para o navegador montar: são JSON e o Excel.
_CABECALHOS_FIXOS = {
    # O navegador não adivinha o tipo: um JSON com "<script>" nunca vira HTML.
    "X-Content-Type-Options": "nosniff",
    # Nenhuma resposta vai para dentro de um <iframe> de outro site (clickjacking). O mesmo
    # que o `frame-ancestors 'none'` da CSP, para navegador antigo que só conhece este.
    "X-Frame-Options": "DENY",
    # O endereço (que pode levar um filtro de busca) não vai para outro site num link.
    "Referrer-Policy": "no-referrer",
    # Outro site não embute a resposta (<img>, <script>) com a sessão de quem o visita. O
    # site é a mesma origem (o proxy do Vite) e o app não é navegador: nenhum dos dois sente.
    "Cross-Origin-Resource-Policy": "same-origin",
    # Dado da fazenda (preços, estoque, usuários, quem tentou entrar, o token do login) não
    # fica no cache do navegador nem de um proxy no caminho. Em toda resposta, e não só nas
    # de /auth, /usuarios e /auditoria: quase tudo aqui é dado da fazenda, nada é estático,
    # e uma regra só não deixa rota nova escapar.
    "Cache-Control": "no-store",
}
# JSON e Excel não carregam nada: a política mais fechada. Se um dia uma resposta for aberta
# como página (um erro que ecoa o que se mandou), nada roda nem é enviado dali.
CSP_DA_API = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
# O Swagger (/docs, fora de produção) é uma página: o JS e o CSS vêm do CDN que o FastAPI
# usa, e o script que o inicia está na própria página. Liberado só aquele script, pelo
# hash, calculado da página que sai (muda com a URL do schema e com a versão do FastAPI),
# e não `'unsafe-inline'`, que deixaria rodar qualquer script injetado. O estilo em linha
# fica liberado: o Swagger escreve atributos `style` nas descrições, e estilo não roda
# código. `connect-src 'self'`: o "Try it out" só fala com esta API.
_CDN_DO_SWAGGER = "https://cdn.jsdelivr.net"
_ICONE_DO_SWAGGER = "https://fastapi.tiangolo.com"
_SCRIPT_EM_LINHA = re.compile(rb"<script>(.*?)</script>", re.DOTALL)


class CabecalhosDeSeguranca:
    """Põe os cabeçalhos de segurança em toda resposta, inclusive nos erros, no 413 do corpo
    e no 500 do registro: por isso fica por fora de todas as outras proteções."""

    def __init__(self, app: ASGIApp, caminho_do_swagger: str | None, hsts_segundos: int) -> None:
        self.app = app
        self.caminho_do_swagger = caminho_do_swagger
        self.cabecalhos = dict(_CABECALHOS_FIXOS)
        if hsts_segundos > 0:
            # Só com HTTPS na frente (ver `hsts_segundos` em app/core/config.py).
            self.cabecalhos["Strict-Transport-Security"] = f"max-age={hsts_segundos}"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope["path"] == self.caminho_do_swagger:
            await self._swagger(scope, receive, send)
            return

        async def enviar(mensagem: Message) -> None:
            if mensagem["type"] == "http.response.start":
                self._por(mensagem, CSP_DA_API)
            await send(mensagem)

        await self.app(scope, receive, enviar)

    async def _swagger(self, scope: Scope, receive: Receive, send: Send) -> None:
        # A página é pequena: junta o corpo para calcular o hash do script antes de mandar
        # os cabeçalhos.
        inicio: Message | None = None
        corpo = bytearray()

        async def juntar(mensagem: Message) -> None:
            nonlocal inicio
            if mensagem["type"] == "http.response.start":
                inicio = mensagem
                return
            if mensagem["type"] != "http.response.body" or inicio is None:
                await send(mensagem)
                return
            corpo.extend(mensagem.get("body", b""))
            if not mensagem.get("more_body", False):
                self._por(inicio, _csp_do_swagger(bytes(corpo)))
                await send(inicio)
                await send({"type": "http.response.body", "body": bytes(corpo)})

        await self.app(scope, receive, juntar)

    def _por(self, inicio: Message, csp: str) -> None:
        cabecalhos = MutableHeaders(scope=inicio)
        for nome, valor in self.cabecalhos.items():
            cabecalhos[nome] = valor
        cabecalhos["Content-Security-Policy"] = csp


def _csp_do_swagger(pagina: bytes) -> str:
    hashes = " ".join(
        f"'sha256-{base64.b64encode(hashlib.sha256(script).digest()).decode()}'"
        for script in _SCRIPT_EM_LINHA.findall(pagina)
    )
    return "; ".join(
        (
            "default-src 'none'",
            f"script-src {_CDN_DO_SWAGGER} {hashes}",
            f"style-src {_CDN_DO_SWAGGER} 'unsafe-inline'",
            f"img-src 'self' data: {_ICONE_DO_SWAGGER}",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'none'",
            "form-action 'none'",
        )
    )
