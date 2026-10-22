"""Modelos ORM. Todo modelo novo é importado aqui, para o Alembic enxergá-lo."""

from app.models.base import Base
from app.models.estoque import Insumo, Movimentacao, Talhao

__all__ = ["Base", "Insumo", "Movimentacao", "Talhao"]
