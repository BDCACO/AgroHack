from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.estoque import Alerta
from app.domain.talhao import ConsumoNoTalhao
from app.schemas.estoque import (
    SEM_CARACTERE_DE_CONTROLE,
    MovimentacaoResposta,
    nas_casas_da_coluna,
)

# Teto da coluna NUMERIC(10, 2).
AREA_MAXIMA = 99_999_999.99


class _Talhao(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nome: str = Field(min_length=1, max_length=120)
    # Maior que zero: é o divisor do custo por hectare.
    # Nas 2 casas da coluna, antes do "maior que zero": 0,004 ha vira 0 e dá 422.
    area_ha: Annotated[float, nas_casas_da_coluna(2)] = Field(gt=0, le=AREA_MAXIMA)
    cultura: str | None = Field(default=None, max_length=60)  # "Soja", "Milho", "Pasto"...


class TalhaoCadastro(_Talhao):
    nome: str = Field(min_length=1, max_length=120, pattern=SEM_CARACTERE_DE_CONTROLE)
    cultura: str | None = Field(default=None, max_length=60, pattern=SEM_CARACTERE_DE_CONTROLE)

    @field_validator("cultura")
    @classmethod
    def _em_branco_e_sem_cultura(cls, cultura: str | None) -> str | None:
        # O campo apagado na tela chega como "": é talhão sem cultura, não cultura "".
        return cultura or None


class TalhaoResposta(_Talhao):
    id: int
    demonstracao: bool
    # Quando a última carência acaba (pode já ter passado). None: nenhuma aplicação de
    # insumo com carência cadastrada. Vale para todas as aplicações, seja qual for o período.
    colheita_liberada_em: date | None
    em_carencia: bool  # colher hoje é proibido
    alertas: list[Alerta]  # a carência, com a conta; vazio quando liberado
    # R$ do que foi aplicado no período, pelo custo médio de hoje. None: houve aplicação e
    # nenhuma tem preço.
    custo_total: float | None
    custo_por_ha: float | None
    limitacoes: list[str]  # o que a carência e o custo não sabem


class TalhaoDetalhe(TalhaoResposta):
    aplicacoes: list[MovimentacaoResposta]  # do período, as mais recentes primeiro
    consumo: list[ConsumoNoTalhao]  # por insumo, no período, o que mais custou primeiro
