from datetime import date
from typing import Literal, Self

from pydantic import Base64Bytes, BaseModel, ConfigDict, Field, model_validator

from app.analysis.consumo import Analise
from app.core.relogio import hoje

# Teto da coluna NUMERIC(12, 3).
QUANTIDADE_MAXIMA = 999_999_999
# Teto da coluna NUMERIC(14, 4).
VALOR_UNITARIO_MAXIMO = 9_999_999_999
# Caractere de controle num nome não aparece na tela, separa nomes que parecem iguais e
# não pode ser gravado numa planilha do Excel.
SEM_CARACTERE_DE_CONTROLE = r"^[^\x00-\x1f\x7f]*$"


class _Insumo(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nome: str = Field(min_length=1, max_length=120)
    unidade: str = Field(min_length=1, max_length=20)
    estoque_minimo: float | None = Field(default=None, ge=0, le=QUANTIDADE_MAXIMA)
    prazo_reposicao_dias: int | None = Field(default=None, ge=0, le=365)
    # Na unidade do insumo (50 para o saco de 50 kg). Opcionais: sem eles, a reposição
    # sugere a quantidade da conta, e a análise diz que não considerou a embalagem.
    embalagem: float | None = Field(default=None, gt=0, le=QUANTIDADE_MAXIMA)
    pedido_minimo: float | None = Field(default=None, ge=0, le=QUANTIDADE_MAXIMA)


class InsumoCadastro(_Insumo):
    # Só na entrada: um nome gravado antes desta regra não pode derrubar a listagem.
    nome: str = Field(min_length=1, max_length=120, pattern=SEM_CARACTERE_DE_CONTROLE)
    unidade: str = Field(min_length=1, max_length=20, pattern=SEM_CARACTERE_DE_CONTROLE)


class InsumoResposta(_Insumo):
    id: int
    demonstracao: bool
    estoque_atual: float
    # R$ por unidade, média das compras com preço ponderada pela quantidade. None sem
    # nenhuma compra com preço.
    custo_medio: float | None
    valor_em_estoque: float | None  # estoque atual (se positivo) × custo médio
    analise: Analise


class _Movimentacao(BaseModel):
    insumo_id: int
    tipo: Literal["entrada", "saida"]
    data: date
    quantidade: float = Field(gt=0, le=QUANTIDADE_MAXIMA)
    validade: date | None = None
    # Movimentação que não é consumo: descarte (saída) ou ajuste de inventário (os dois
    # lados). Sem motivo, a saída é uma retirada para uso.
    motivo: Literal["descarte", "inventario"] | None = None
    # R$ por unidade do insumo, o preço pago. Só numa compra; opcional.
    valor_unitario: float | None = Field(default=None, gt=0, le=VALOR_UNITARIO_MAXIMO)


class MovimentacaoEntrada(_Movimentacao):
    # O ajuste de inventário só nasce da contagem (POST /insumos/{id}/inventario), que
    # calcula a diferença: lançado à mão, seria um número sem conferência.
    motivo: Literal["descarte"] | None = None

    @model_validator(mode="after")
    def _coerente(self) -> Self:
        if self.validade is not None and self.tipo != "entrada":
            raise ValueError("validade só se informa numa entrada: é ela que traz o lote")
        if self.motivo is not None and self.tipo != "saida":
            raise ValueError("descarte é uma saída: o produto deixa o estoque")
        if self.valor_unitario is not None and self.tipo != "entrada":
            raise ValueError("valor_unitario só se informa numa entrada: é o preço da compra")
        # Ano digitado errado (2062 por 2026) jogaria a movimentação no futuro.
        if self.data > hoje():
            raise ValueError("a data da movimentação não pode ser futura")
        return self


class MovimentacaoResposta(_Movimentacao):
    model_config = ConfigDict(from_attributes=True)

    id: int


class ContagemDeInventario(BaseModel):
    quantidade_contada: float = Field(ge=0, le=QUANTIDADE_MAXIMA)
    data: date = Field(default_factory=hoje)

    @model_validator(mode="after")
    def _no_passado(self) -> Self:
        if self.data > hoje():
            raise ValueError("a data da contagem não pode ser futura")
        return self


class AjusteDeInventario(BaseModel):
    # O que os registros diziam no fim do dia da contagem.
    saldo_registrado: float
    quantidade_contada: float
    diferenca: float  # positiva = sobra; negativa = falta
    movimentacao: MovimentacaoResposta | None  # None quando a contagem bate


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
