"""Ajustes da fazenda inteira: uma implantação do CampoCerto é uma fazenda só, então é
uma linha só (sem fazenda_id)."""

from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Configuracao(Base):
    __tablename__ = "configuracoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 1 a 12; vazio = sazonalidade desligada, o motor de análise não considera a época do
    # ano em nada (como sempre foi).
    meses_de_safra: Mapped[list[int]] = mapped_column(JSON, default=list)
