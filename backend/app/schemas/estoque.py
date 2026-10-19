from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.analysis.consumo import Analise
from app.core.relogio import hoje

# Teto da coluna NUMERIC(12, 3).
QUANTIDADE_MAXIMA = 999_999_999


class InsumoCadastro(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nome: str = Field(min_length=1, max_length=120)
    unidade: str = Field(min_length=1, max_length=20)
    estoque_minimo: float | None = Field(default=None, ge=0, le=QUANTIDADE_MAXIMA)
    prazo_reposicao_dias: int | None = Field(default=None, ge=0, le=365)


class InsumoResposta(InsumoCadastro):
    id: int
    demonstracao: bool
    estoque_atual: float
    analise: Analise


class _Movimentacao(BaseModel):
    insumo_id: int
    tipo: Literal["entrada", "saida"]
    data: date
    quantidade: float = Field(gt=0, le=QUANTIDADE_MAXIMA)
    validade: date | None = None


class MovimentacaoEntrada(_Movimentacao):
    @model_validator(mode="after")
    def _coerente(self) -> Self:
        if self.validade is not None and self.tipo != "entrada":
            raise ValueError("validade só se informa numa entrada: é ela que traz o lote")
        # Ano digitado errado (2062 por 2026) jogaria a movimentação no futuro.
        if self.data > hoje():
            raise ValueError("a data da movimentação não pode ser futura")
        return self


class MovimentacaoResposta(_Movimentacao):
    model_config = ConfigDict(from_attributes=True)

    id: int


class PedidoDeImportacao(BaseModel):
    # O texto do CSV, já decodificado pelo navegador. 5 MB passam de dezenas de
    # milhares de linhas: anos de registro de uma propriedade.
    conteudo: str = Field(max_length=5_000_000)
    # Falso = só confere e resume, para o produtor ver antes de gravar.
    confirmar: bool = False
