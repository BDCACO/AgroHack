"""Agrega as rotas da v1. Cada recurso novo entra com uma linha aqui."""

from fastapi import APIRouter

from app.api.routes import health, insumos, movimentacoes

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(insumos.router)
api_router.include_router(movimentacoes.router)
