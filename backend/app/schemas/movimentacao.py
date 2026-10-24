import uuid
from datetime import date, datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.estoque import TipoMovimentacao
from app.schemas.comum import Quantidade, texto


class MovimentacaoEntrada(BaseModel):
    insumo_id: uuid.UUID
    tipo: TipoMovimentacao
    quantidade: Quantidade = Field(gt=0)
    data: date
    # Validade do lote comprado. Retirada não tem lote próprio.
    validade: date | None = None
    observacao: Annotated[str, texto(500)] | None = None

    @model_validator(mode="after")
    def validade_so_em_compra(self) -> Self:
        if self.tipo is TipoMovimentacao.RETIRADA and self.validade is not None:
            raise ValueError("validade só se informa em compra")
        return self


class MovimentacaoSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    insumo_id: uuid.UUID
    insumo_nome: str
    insumo_unidade: str
    tipo: TipoMovimentacao
    quantidade: Quantidade
    data: date
    validade: date | None
    observacao: str | None
    criado_em: datetime
