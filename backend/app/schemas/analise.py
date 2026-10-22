from datetime import date
from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.schemas.estoque import DadosDoInsumo


class InsumoEntrada(DadosDoInsumo):
    # Negativo é aceito: o motor o aponta como inconsistência nos registros.
    estoque_atual: float
    # R$ por unidade. Opcional: sem ele, a análise é a mesma, só não fala em reais.
    custo_medio: float | None = Field(default=None, gt=0)


class RetiradaEntrada(BaseModel):
    data: date
    quantidade: float = Field(gt=0)


class LoteEntrada(BaseModel):
    quantidade: float = Field(ge=0)
    validade: date


class PedidoDeAnalise(BaseModel):
    insumo: InsumoEntrada
    retiradas: list[RetiradaEntrada] = Field(default=[], max_length=100_000)
    lotes: list[LoteEntrada] = Field(default=[], max_length=1_000)
    # Desde quando as retiradas estão completas: separa "não houve consumo" de
    # "não havia registro".
    registros_desde: date
    referencia: date

    @model_validator(mode="after")
    def _periodo_valido(self) -> Self:
        if self.registros_desde > self.referencia:
            raise ValueError("registros_desde não pode ser depois de referencia")
        return self
