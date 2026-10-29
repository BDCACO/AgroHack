import math
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import Base64Bytes, BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from app.analysis.consumo import Analise
from app.core.relogio import hoje

# Teto da coluna NUMERIC(12, 3).
QUANTIDADE_MAXIMA = 999_999_999
# Teto da coluna NUMERIC(14, 4).
VALOR_UNITARIO_MAXIMO = 9_999_999_999
# Lançamentos por lote da sincronização: semanas de fila de um celular cabem com folga, e
# 500 itens (uns 100 kB) ficam longe do limite de 8 MB do corpo (app/main.py).
LOTE_MAXIMO = 500
# Caractere de controle num nome não aparece na tela, separa nomes que parecem iguais e
# não pode ser gravado numa planilha do Excel.
SEM_CARACTERE_DE_CONTROLE = r"^[^\x00-\x1f\x7f]*$"


def como_o_banco(valor: float, casas: int) -> float:
    """O número como a coluna NUMERIC do PostgreSQL o guarda: lido com 15 dígitos e com o
    meio arredondado para longe do zero. O round() do Python arredonda pelo valor binário
    do float e discorda nos meios (1.2345 vira 1,234 lá e 1,235 no banco)."""
    return float(Decimal(f"{valor:.15g}").quantize(Decimal(1).scaleb(-casas), ROUND_HALF_UP))


def nas_casas_da_coluna(casas: int) -> BeforeValidator:
    """Arredonda ANTES das regras do campo: 0,0004 numa coluna de 3 casas vira 0, e o
    "maior que zero" o recusa com 422, em vez de o banco recusá-lo depois com um 500."""

    def arredondar(valor: object) -> object:
        # Só número finito e de tamanho plausível; o resto segue para a validação de sempre.
        numero = isinstance(valor, int | float) and not isinstance(valor, bool)
        if numero and math.isfinite(valor) and abs(valor) < 1e15:
            return como_o_banco(valor, casas)
        return valor

    return BeforeValidator(arredondar)


# As casas das colunas NUMERIC(12, 3) e NUMERIC(14, 4).
NaColunaDeQuantidade = Annotated[float, nas_casas_da_coluna(3)]
NaColunaDePreco = Annotated[float, nas_casas_da_coluna(4)]


class _Insumo(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nome: str = Field(min_length=1, max_length=120)
    unidade: str = Field(min_length=1, max_length=20)
    estoque_minimo: NaColunaDeQuantidade | None = Field(default=None, ge=0, le=QUANTIDADE_MAXIMA)
    prazo_reposicao_dias: int | None = Field(default=None, ge=0, le=365)
    # Na unidade do insumo (50 para o saco de 50 kg). Opcionais: sem eles, a reposição
    # sugere a quantidade da conta, e a análise diz que não considerou a embalagem.
    embalagem: NaColunaDeQuantidade | None = Field(default=None, gt=0, le=QUANTIDADE_MAXIMA)
    pedido_minimo: NaColunaDeQuantidade | None = Field(default=None, ge=0, le=QUANTIDADE_MAXIMA)


class DadosDoInsumo(_Insumo):
    """O que o motor de análise usa, com nome e unidade conferidos como foram digitados."""

    # Só na entrada: um nome gravado antes desta regra não pode derrubar a listagem.
    nome: str = Field(min_length=1, max_length=120, pattern=SEM_CARACTERE_DE_CONTROLE)
    unidade: str = Field(min_length=1, max_length=20, pattern=SEM_CARACTERE_DE_CONTROLE)


class InsumoCadastro(DadosDoInsumo):
    # Dias mínimos entre aplicar e colher ou abater, da bula. 0 = não tem carência (a
    # ureia); vazio = não informada. Fica fora do motor de análise (e de POST /analises):
    # é regra do talhão onde o insumo foi aplicado, não do estoque.
    carencia_dias: int | None = Field(default=None, ge=0, le=365)
    # Fertilizante, defensivo, nutrição animal... (GET /categorias). Opcional, e como a
    # embalagem: o PUT sem ela mantém a gravada.
    categoria_id: int | None = None
    # O código de barras de fábrica, ensinado pelo app na primeira leitura. Como a
    # categoria: o PUT sem ele mantém o gravado.
    codigo_de_barras: str | None = Field(default=None, min_length=1, max_length=64)


class InsumoResposta(_Insumo):
    id: int
    demonstracao: bool
    carencia_dias: int | None
    categoria_id: int | None = None
    categoria: str | None = None  # o nome, para a tela não precisar de outra consulta
    codigo_de_barras: str | None = None
    estoque_atual: float
    # R$ por unidade, média das compras com preço ponderada pela quantidade. None sem
    # nenhuma compra com preço.
    custo_medio: float | None
    valor_em_estoque: float | None  # estoque atual (se positivo) × custo médio
    # O que já foi pedido (pedidos abertos ou parciais) e ainda não chegou. A análise o
    # desconta da reposição, e o alerta de falta diz se ele chega a tempo.
    em_pedido: float = 0
    # A previsão de chegada mais distante entre esses pedidos (None sem pedido com data).
    chegada_prevista: date | None = None
    analise: Analise


class _Movimentacao(BaseModel):
    insumo_id: int
    tipo: Literal["entrada", "saida"]
    data: date
    quantidade: NaColunaDeQuantidade = Field(gt=0, le=QUANTIDADE_MAXIMA)
    validade: date | None = None
    # Movimentação que não é consumo: descarte (saída) ou ajuste de inventário (os dois
    # lados). Sem motivo, a saída é uma retirada para uso.
    motivo: Literal["descarte", "inventario"] | None = None
    # R$ por unidade do insumo, o preço pago. Só numa compra; opcional.
    valor_unitario: NaColunaDePreco | None = Field(default=None, gt=0, le=VALOR_UNITARIO_MAXIMO)
    # Identificador que o app gera para cada lançamento (UUID v4): reenviar o mesmo
    # lançamento não o grava de novo. Opcional: o site não manda.
    uuid: UUID | None = None
    # Onde o insumo foi aplicado, só numa retirada para uso. Opcional: o site e o app de
    # antes não mandam, e a retirada sem talhão vale como sempre.
    talhao_id: int | None = None
    # De quem se comprou, só numa compra. Opcional, como o talhão.
    fornecedor_id: int | None = None


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
        if self.talhao_id is not None and (self.tipo != "saida" or self.motivo is not None):
            raise ValueError(
                "talhão só se informa numa retirada para uso: é onde o insumo foi aplicado"
            )
        if self.fornecedor_id is not None and (self.tipo != "entrada" or self.motivo is not None):
            raise ValueError("fornecedor só se informa numa compra (entrada): é de quem se comprou")
        # Ano digitado errado (2062 por 2026) jogaria a movimentação no futuro.
        if self.data > hoje():
            raise ValueError("a data da movimentação não pode ser futura")
        return self


class MovimentacaoResposta(_Movimentacao):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # Quem lançou (auditoria), só na resposta: o autor é quem está logado, e não quem o
    # pedido diz ser. Vazio no que veio sem login (autenticação desligada) ou de antes dela.
    usuario_id: int | None = None
    lancado_por: str | None = None  # o nome dele, para a tela não precisar de outra consulta
    comprado_de: str | None = None  # o nome do fornecedor, pelo mesmo motivo
    # A linha do pedido de compra que esta entrada recebeu (POST /pedidos/{id}/receber).
    # Só na resposta: a entrada de um pedido nasce do recebimento, que confere o pedido.
    item_do_pedido_id: int | None = None


class MovimentacaoDoLote(MovimentacaoEntrada):
    # Na fila do app, o uuid é o que torna o reenvio seguro: sem ele, o item é recusado.
    uuid: UUID


class LoteDeMovimentacoes(BaseModel):
    """A fila de lançamentos que o app guardou sem sinal, na ordem em que foram feitos."""

    # Itens genéricos: cada um é validado sozinho, no serviço, e um item malformado vira
    # `recusada`, em vez de um 422 que travaria a fila inteira no celular.
    movimentacoes: list[Any] = Field(max_length=LOTE_MAXIMO)


class ResultadoDoItem(BaseModel):
    # Volta o uuid enviado, para o app achar o item na fila; None se o item não trouxe
    # um uuid legível (a ordem dos resultados é a do envio).
    uuid: UUID | None
    situacao: Literal["gravada", "ja_existia", "recusada"]
    movimentacao: MovimentacaoResposta | None = None  # quando gravada ou já existia
    erros: list[str] = []  # por que foi recusada, em frases para a tela
    avisos: list[str] = []  # não impedem a gravação: só pedem para conferir


class ResumoDoLote(BaseModel):
    gravadas: int
    ja_existiam: int
    recusadas: int


class ResultadoDoLote(BaseModel):
    resultados: list[ResultadoDoItem]  # na ordem do envio
    resumo: ResumoDoLote


class ContagemDeInventario(BaseModel):
    quantidade_contada: NaColunaDeQuantidade = Field(ge=0, le=QUANTIDADE_MAXIMA)
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


class PrecoPago(BaseModel):
    """O que se pagou a um fornecedor por um insumo: é o que permite comparar revendas."""

    insumo_id: int
    insumo: str
    unidade: str
    fornecedor_id: int
    fornecedor: str
    compras: int
    quantidade: float  # o total comprado dele
    # Média do preço pago ponderada pela quantidade, das compras com preço (a mesma regra do
    # custo médio). None se nenhuma compra dele tem preço.
    preco_medio: float | None
    ultimo_preco: float | None  # o da compra com preço mais recente
    ultima_compra: date


class InsumoDetalhe(InsumoResposta):
    # Um ponto por dia com movimentação, do mais antigo ao mais recente.
    historico: list[PontoDeEstoque]
    movimentacoes: list[MovimentacaoResposta]  # as mais recentes primeiro
    # O preço médio pago a cada fornecedor, o mais barato primeiro.
    precos_por_fornecedor: list[PrecoPago] = []


class AlertasPorGravidade(BaseModel):
    alta: int
    media: int
    baixa: int


class Perdas(BaseModel):
    """Descartes e faltas da contagem do galpão, em R$, pelo custo médio do insumo. Insumo
    sem preço fica de fora (as limitações do resumo dizem quantos)."""

    ultimos_30_dias: float
    total: float


class ComprasSugeridas(BaseModel):
    # Soma do custo estimado das reposições a pedir nos próximos 30 dias; None se
    # nenhuma delas tem preço.
    valor: float | None
    pedidos: int  # quantas reposições caem nos próximos 30 dias
    pedir_hoje: int


class Resumo(BaseModel):
    """A visão geral em reais, para o Painel e o app."""

    insumos: int
    valor_em_estoque: float | None  # None se nenhum insumo tem custo médio
    insumos_sem_preco: int  # sem nenhuma compra com preço
    perdas: Perdas
    compras_sugeridas: ComprasSugeridas
    # Só os dos insumos: a carência é do talhão, e vem contada à parte.
    alertas: AlertasPorGravidade
    talhoes_em_carencia: int  # onde colher hoje é proibido (GET /talhoes diz até quando)
    # O que as somas não sabem, como a análise de cada insumo.
    limitacoes: list[str]


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
