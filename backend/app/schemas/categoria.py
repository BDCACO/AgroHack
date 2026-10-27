from pydantic import BaseModel, ConfigDict, Field

from app.schemas.estoque import SEM_CARACTERE_DE_CONTROLE


class CategoriaCadastro(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    # Curto: aparece no filtro da lista de insumos e na legenda do gráfico.
    nome: str = Field(min_length=1, max_length=60, pattern=SEM_CARACTERE_DE_CONTROLE)


class CategoriaResposta(BaseModel):
    id: int
    nome: str
    insumos: int  # quantos insumos estão nela: com algum, ela não se remove
