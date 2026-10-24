import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.comum import Quantidade, texto


class InsumoEntrada(BaseModel):
    nome: Annotated[str, texto(120)]
    categoria: Annotated[str, texto(80)] | None = None
    unidade: Annotated[str, texto(20)] = Field(examples=["kg", "L", "saco 50 kg"])
    estoque_minimo: Quantidade = Field(ge=0)


class InsumoSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    categoria: str | None
    unidade: str
    estoque_minimo: Quantidade
    # Calculado das movimentações (ver app/domain/estoque.py), nunca gravado.
    saldo_atual: Quantidade
    criado_em: datetime
