"""Agrega as rotas da v1. Cada recurso novo entra com uma linha aqui."""

from fastapi import APIRouter, Depends

from app.api.permissoes import exigir_sessao
from app.api.routes import analises, autenticacao, estoque, health, talhoes

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(autenticacao.publico)
api_router.include_router(autenticacao.router, dependencies=[Depends(exigir_sessao)])
api_router.include_router(estoque.router)
api_router.include_router(talhoes.router)
api_router.include_router(analises.router)
