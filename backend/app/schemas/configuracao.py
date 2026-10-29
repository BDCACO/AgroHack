from pydantic import BaseModel, Field, field_validator


class ConfiguracaoCadastro(BaseModel):
    # 1 (janeiro) a 12 (dezembro); vazio desliga a sazonalidade na análise.
    meses_de_safra: list[int] = Field(default_factory=list, max_length=12)

    @field_validator("meses_de_safra")
    @classmethod
    def _dentro_do_ano(cls, meses: list[int]) -> list[int]:
        if any(not (1 <= mes <= 12) for mes in meses):
            raise ValueError("mês deve estar entre 1 e 12")
        return sorted(set(meses))


class ConfiguracaoResposta(BaseModel):
    meses_de_safra: list[int]
