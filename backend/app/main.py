import logging

from fastapi import FastAPI

from app.api.erros import registrar_tratadores
from app.api.router import api_router
from app.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Fábrica da aplicação — os testes criam a sua com Settings próprios."""
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)

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
    app.include_router(api_router, prefix=prefixo)
    registrar_tratadores(app)
    return app


app = create_app()
