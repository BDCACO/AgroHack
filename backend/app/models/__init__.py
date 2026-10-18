"""Modelos ORM. Todo modelo novo é importado aqui, para o Alembic enxergá-lo."""

from app.models.base import Base

__all__ = ["Base"]
