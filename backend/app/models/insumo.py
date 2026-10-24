import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Insumo(Base):
    __tablename__ = "insumo"

    # uuid v7: ordenável pelo tempo de criação e não enumerável como um serial.
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    nome: Mapped[str] = mapped_column(String(120))
    categoria: Mapped[str | None] = mapped_column(String(80))
    unidade: Mapped[str] = mapped_column(String(20))
    estoque_minimo: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# Nome único sem diferenciar maiúsculas: "Ureia" e "ureia" são o mesmo produto.
Index("uq_insumo_nome_lower", func.lower(Insumo.nome), unique=True)
