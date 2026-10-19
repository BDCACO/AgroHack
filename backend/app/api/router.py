"""Agrega as rotas da v1. Cada recurso novo entra com uma linha aqui."""

from fastapi import APIRouter

from app.api.routes import analises, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(analises.router)
