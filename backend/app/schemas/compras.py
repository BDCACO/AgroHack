from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.estoque import SEM_CARACTERE_DE_CONTROLE, MovimentacaoResposta, PrecoPago

# A observação é texto corrido e pode ter quebra de linha e tabulação; o resto dos
# caracteres de controle (o NUL, que o PostgreSQL nem aceita) não.
TEXTO_CORRIDO = r"^[^\x00-\x08\x0b\x0c\x0e-\x1f\x7f]*$"


class _Fornecedor(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nome: str = Field(min_length=1, max_length=120)
    contato: str | None = Field(default=None, max_length=120)  # com quem falar
    telefone: str | None = Field(default=None, max_length=30)  # o WhatsApp da revenda
    cidade: str | None = Field(default=None, max_length=80)
    observacao: str | None = Field(default=None, max_length=500)
    # Desativado sai das escolhas (novo pedido, sugestão de compra); as compras ficam.
    ativo: bool = True


class FornecedorCadastro(_Fornecedor):
    nome: str = Field(min_length=1, max_length=120, pattern=SEM_CARACTERE_DE_CONTROLE)
    contato: str | None = Field(default=None, max_length=120, pattern=SEM_CARACTERE_DE_CONTROLE)
    telefone: str | None = Field(default=None, max_length=30, pattern=SEM_CARACTERE_DE_CONTROLE)
    cidade: str | None = Field(default=None, max_length=80, pattern=SEM_CARACTERE_DE_CONTROLE)
    observacao: str | None = Field(default=None, max_length=500, pattern=TEXTO_CORRIDO)

    @field_validator("contato", "telefone", "cidade", "observacao")
    @classmethod
    def _em_branco_e_vazio(cls, texto: str | None) -> str | None:
        # O campo apagado na tela chega como "": é fornecedor sem telefone, não telefone "".
        return texto or None


class FornecedorResposta(_Fornecedor):
    model_config = ConfigDict(from_attributes=True)

    id: int
    demonstracao: bool


class FornecedorDetalhe(FornecedorResposta):
    compras: list[MovimentacaoResposta]  # as mais recentes primeiro, até 20
    precos: list[PrecoPago]  # o que se pagou a ele por cada insumo, pelo nome do insumo
