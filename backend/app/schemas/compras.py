from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.relogio import hoje
from app.schemas.estoque import (
    QUANTIDADE_MAXIMA,
    SEM_CARACTERE_DE_CONTROLE,
    VALOR_UNITARIO_MAXIMO,
    MovimentacaoResposta,
    NaColunaDePreco,
    NaColunaDeQuantidade,
    PrecoPago,
)

# Linhas num pedido: uma revenda não vende cem produtos de uma vez a uma fazenda.
ITENS_MAXIMOS = 100

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


Situacao = Literal["aberto", "parcial", "recebido", "cancelado"]


class ItemDoPedidoEntrada(BaseModel):
    insumo_id: int
    quantidade: NaColunaDeQuantidade = Field(gt=0, le=QUANTIDADE_MAXIMA)
    # R$ por unidade combinado com a revenda. Opcional: a entrada recebida o herda.
    valor_unitario: NaColunaDePreco | None = Field(default=None, gt=0, le=VALOR_UNITARIO_MAXIMO)


class PedidoEntrada(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    # Opcional: o pedido feito a quem ainda não está cadastrado vale igual.
    fornecedor_id: int | None = None
    feito_em: date = Field(default_factory=hoje)
    # Sem ela, a análise desconta o pedido, mas não sabe se ele chega antes de o estoque
    # acabar, e diz isso nas limitações.
    previsto_para: date | None = None
    observacao: str | None = Field(default=None, max_length=500, pattern=TEXTO_CORRIDO)
    itens: list[ItemDoPedidoEntrada] = Field(min_length=1, max_length=ITENS_MAXIMOS)

    @field_validator("observacao")
    @classmethod
    def _em_branco_e_vazia(cls, texto: str | None) -> str | None:
        return texto or None

    @model_validator(mode="after")
    def _coerente(self) -> Self:
        if self.feito_em > hoje():
            raise ValueError("a data do pedido não pode ser futura")
        if self.previsto_para is not None and self.previsto_para < self.feito_em:
            raise ValueError("a previsão de chegada não pode ser antes do pedido")
        insumos = [item.insumo_id for item in self.itens]
        if len(set(insumos)) < len(insumos):
            # Uma linha por insumo: o recebimento aponta para ela sem ambiguidade.
            raise ValueError(
                "o mesmo insumo aparece em mais de uma linha do pedido: some as quantidades "
                "numa linha só"
            )
        return self


class ItemDoPedidoResposta(BaseModel):
    id: int  # o que o recebimento informa (`item_id`)
    insumo_id: int
    insumo: str
    unidade: str
    quantidade: float
    valor_unitario: float | None
    quantidade_recebida: float  # pode passar da quantidade: veio a mais
    falta_receber: float  # nunca negativa


class PedidoResposta(BaseModel):
    id: int
    fornecedor_id: int | None
    fornecedor: str | None  # o nome, para a tela não precisar de outra consulta
    situacao: Situacao
    feito_em: date
    previsto_para: date | None
    observacao: str | None
    usuario_id: int | None  # quem fez o pedido; vazio sem login
    feito_por: str | None
    # A previsão já passou e ainda falta chegar: hora de cobrar a revenda.
    atrasado: bool
    # Soma de quantidade × preço combinado das linhas com preço; None se nenhuma tem.
    custo_estimado: float | None
    itens: list[ItemDoPedidoResposta]
