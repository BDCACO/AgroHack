from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.estoque import SEM_CARACTERE_DE_CONTROLE

# Teto da coluna NUMERIC(10, 2).
AREA_MAXIMA = 99_999_999.99


class _Talhao(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nome: str = Field(min_length=1, max_length=120)
    # Maior que zero: é o divisor do custo por hectare.
    area_ha: float = Field(gt=0, le=AREA_MAXIMA)
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
    model_config = ConfigDict(from_attributes=True)

    id: int
    demonstracao: bool
