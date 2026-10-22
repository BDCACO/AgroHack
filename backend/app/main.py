import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import Settings, get_settings

# Folga sobre o maior pedido legítimo: a planilha de 5 MB vira uns 6,7 MB em base64.
CORPO_MAXIMO = 8_000_000


def create_app(settings: Settings | None = None) -> FastAPI:
    """Fábrica da aplicação — os testes criam a sua com Settings próprios."""
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)
    if not settings.autenticacao:
        logging.getLogger(__name__).warning(
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

    return app


app = create_app()
