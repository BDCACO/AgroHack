"""Modelos ORM. Todo modelo novo é importado aqui, para o Alembic enxergá-lo."""

from app.models.base import Base
from app.models.insumo import Insumo
from app.models.movimentacao import Movimentacao

__all__ = ["Base", "Insumo", "Movimentacao"]
