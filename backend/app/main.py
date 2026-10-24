import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolSemConexao

from app.api.router import api_router
from app.core.config import Settings, get_settings

# Folga sobre o maior pedido legítimo: a planilha de 5 MB vira uns 6,7 MB em base64.
CORPO_MAXIMO = 8_000_000

logger = logging.getLogger(__name__)

# Os tempos-limite do banco (app/core/database.py), pelo código do PostgreSQL: o comando
# que passou do statement_timeout e a espera por trava que passou do lock_timeout.
TEMPO_LIMITE_DO_BANCO = {
    "57014": "O banco demorou demais para responder. Tente de novo em alguns segundos.",
    "55P03": (
        "Outro pedido está mexendo nos mesmos dados agora. Tente de novo em alguns segundos."
    ),
}
# Em segundos: o lock_timeout padrão. Quem segurava a trava já terminou, quase sempre.
TENTE_DE_NOVO_EM = "5"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Fábrica da aplicação — os testes criam a sua com Settings próprios."""
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)
    if not settings.autenticacao:
        logger.warning(
            "AUTENTICACAO desligada: qualquer um que alcance a API lê e altera tudo. "
            "Só para desenvolvimento; em produção a API nem sobe assim."
        )

    docs = settings.docs_habilitadas
    prefixo = settings.api_v1_prefix
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        # Sob o prefixo da API, para passarem pelo mesmo proxy do Vite que /api.
        docs_url=f"{prefixo}/docs" if docs else None,
        redoc_url=None,
        openapi_url=f"{prefixo}/openapi.json" if docs else None,
    )
    # As permissões (app/api/permissoes.py) leem daqui se a autenticação está ligada: é a
    # configuração deste app, e não a do ambiente, que os testes trocam.
    app.state.settings = settings
    app.include_router(api_router, prefix=prefixo)

    @app.middleware("http")
    async def limitar_o_corpo(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Sem isto, o corpo inteiro iria para a memória antes de qualquer validação.
        # ponytail: confia no Content-Length; pedido "chunked" sem ele passa — limitar
        # no proxy reverso se a API sair da rede da fazenda.
        tamanho = request.headers.get("content-length", "")
        if tamanho.isdigit() and int(tamanho) > CORPO_MAXIMO:
            return JSONResponse(
                {"detail": "Arquivo grande demais: o máximo é 5 MB."}, status_code=413
            )
        return await call_next(request)

    @app.exception_handler(DataError)
    async def dado_que_o_banco_recusa(_: Request, __: DataError) -> JSONResponse:
        # Um id maior que o `integer` do PostgreSQL ou um texto com caractere nulo passam
        # pela validação (o SQLite dos testes os aceita) e o banco os recusa. É dado
        # inválido do pedido, não defeito do servidor: 422, e não 500 com traceback no log.
        return JSONResponse(
            {"detail": "Algum valor do pedido está fora do que o sistema aceita."},
            status_code=422,
        )

    @app.exception_handler(OperationalError)
    async def banco_demorou(_: Request, erro: OperationalError) -> JSONResponse:
        # 503 com Retry-After, e não 500 com traceback: não é defeito do servidor nem do
        # pedido, é espera que passa, e quem chamou (o site, a fila do app) tenta de novo.
        # Nem 409 (não há o que o produtor corrigir) nem 504 (a API não é um proxy).
        codigo = getattr(erro.orig, "sqlstate", None)
        if codigo not in TEMPO_LIMITE_DO_BANCO:
            # Banco fora do ar, senha errada: não passa sozinho; segue como erro.
            raise erro
        # Só o código: a consulta e os valores dela podem ter dado do produtor.
        logger.warning("Tempo-limite do banco estourado (SQLSTATE %s).", codigo)
        return _tente_de_novo(TEMPO_LIMITE_DO_BANCO[codigo])

    @app.exception_handler(PoolSemConexao)
    async def sem_conexao_livre(_: Request, __: PoolSemConexao) -> JSONResponse:
        logger.warning("Nenhuma conexão livre no pool do banco a tempo.")
        return _tente_de_novo("O sistema está ocupado agora. Tente de novo em alguns segundos.")

    return app


def _tente_de_novo(frase: str) -> JSONResponse:
    return JSONResponse(
        {"detail": frase}, status_code=503, headers={"Retry-After": TENTE_DE_NOVO_EM}
    )


app = create_app()
