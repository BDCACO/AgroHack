from datetime import date
from typing import Literal, Self

from pydantic import Base64Bytes, BaseModel, ConfigDict, Field, model_validator

from app.analysis.consumo import Analise
from app.core.relogio import hoje

# Teto da coluna NUMERIC(12, 3).
QUANTIDADE_MAXIMA = 999_999_999
# Caractere de controle num nome não aparece na tela, separa nomes que parecem iguais e
# não pode ser gravado numa planilha do Excel.
SEM_CARACTERE_DE_CONTROLE = r"^[^\x00-\x1f\x7f]*$"


class InsumoCadastro(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nome: str = Field(min_length=1, max_length=120, pattern=SEM_CARACTERE_DE_CONTROLE)
    unidade: str = Field(min_length=1, max_length=20, pattern=SEM_CARACTERE_DE_CONTROLE)
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


class PontoDeEstoque(BaseModel):
    data: date
    saldo: float  # no fim do dia


class InsumoDetalhe(InsumoResposta):
    # Um ponto por dia com movimentação, do mais antigo ao mais recente.
    historico: list[PontoDeEstoque]
    movimentacoes: list[MovimentacaoResposta]  # as mais recentes primeiro


class PedidoDeImportacao(BaseModel):
    """Um dos dois: a planilha do Excel ou o texto do CSV (que o navegador decodifica). 5 MB
    passam de dezenas de milhares de linhas: anos de registro de uma propriedade."""

    xlsx: Base64Bytes | None = Field(default=None, max_length=5_000_000)
    conteudo: str | None = Field(default=None, max_length=5_000_000)
    # Falso = só confere e resume, para o produtor ver antes de gravar.
    confirmar: bool = False

    @model_validator(mode="after")
    def _um_arquivo(self) -> Self:
        if (self.xlsx is None) == (self.conteudo is None):
            raise ValueError("envie a planilha em `xlsx` (base64) ou o CSV em `conteudo`")
        return self
