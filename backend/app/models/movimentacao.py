import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.estoque import TipoMovimentacao
from app.models.base import Base
from app.models.insumo import Insumo


class Movimentacao(Base):
    __tablename__ = "movimentacao"
    # As mesmas regras do schema Pydantic, repetidas no banco: o banco é a
    # última linha de defesa contra um caminho que não passe pela API.
    __table_args__ = (
        CheckConstraint("quantidade > 0", name="quantidade_positiva"),
        CheckConstraint("tipo = 'compra' OR validade IS NULL", name="validade_so_em_compra"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    # RESTRICT: apagar insumo com histórico é recusado pelo serviço, e o banco garante.
    insumo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("insumo.id", ondelete="RESTRICT"), index=True
    )
    tipo: Mapped[TipoMovimentacao] = mapped_column(
        Enum(
            TipoMovimentacao,
            name="tipo_movimentacao",
            values_callable=lambda tipos: [t.value for t in tipos],
        )
    )
    quantidade: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    data: Mapped[date] = mapped_column(Date, index=True)
    validade: Mapped[date | None] = mapped_column(Date)
    observacao: Mapped[str | None] = mapped_column(String(500))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    insumo: Mapped[Insumo] = relationship(lazy="joined")
