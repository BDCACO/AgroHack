// Espelho dos schemas de backend/app/schemas/ e do `Analise` do motor. Escrito à mão;
// gerar a partir do OpenAPI (como faz o ArkoHub) é decisão pendente — ver
// docs/ARQUITETURA.md, "Próximas decisões".

export interface HealthResponse {
  status: 'ok'
}

export interface ReadinessResponse {
  status: 'pronto' | 'indisponivel'
  database: 'ok' | 'erro'
}

export type Gravidade = 'alta' | 'media' | 'baixa'

export type TipoAlerta =
  | 'abaixo_do_minimo'
  | 'risco_de_falta'
  | 'vencido'
  | 'vencimento_proximo'
  | 'excesso'
  | 'baixa_movimentacao'
  | 'consumo_incomum'

export interface Alerta {
  tipo: TipoAlerta
  gravidade: Gravidade
  justificativa: string
}

export interface Reposicao {
  pedir_em: string // AAAA-MM-DD
  pedir_hoje: boolean // decidido pela API, na data de Rondônia
  quantidade: number
  justificativa: string
  custo_estimado: number | null // quantidade × custo médio; null sem preço nas compras
}

export interface Analise {
  consumo_diario: number | null
  cobertura_dias: number | null
  alertas: Alerta[]
  reposicao: Reposicao | null
  limitacoes: string[]
}

export interface InsumoCadastro {
  nome: string
  unidade: string
  estoque_minimo: number | null
  prazo_reposicao_dias: number | null
  // Na unidade do insumo (50 para o saco de 50 kg): a reposição sai em embalagens fechadas.
  embalagem: number | null
  pedido_minimo: number | null
}

export interface Insumo extends InsumoCadastro {
  id: number
  demonstracao: boolean // gerado por `make demo`: não é dado real
  carencia_dias: number | null
  estoque_atual: number
  custo_medio: number | null // R$ por unidade, das compras com preço
  valor_em_estoque: number | null // estoque atual (se positivo) × custo médio
  analise: Analise
}

export interface MovimentacaoEntrada {
  insumo_id: number
  tipo: 'entrada' | 'saida'
  data: string // AAAA-MM-DD
  quantidade: number
  validade: string | null
  valor_unitario?: number | null // R$ por unidade, só numa entrada (o preço da compra)
}

export interface Movimentacao extends MovimentacaoEntrada {
  id: number
  motivo?: 'descarte' | 'inventario' | null
}

export interface PontoDeEstoque {
  data: string // AAAA-MM-DD
  saldo: number // no fim do dia
}

export interface InsumoDetalhe extends Insumo {
  historico: PontoDeEstoque[] // um ponto por dia com movimentação, do mais antigo
  movimentacoes: Movimentacao[] // as mais recentes primeiro
}

/** A planilha do Excel em base64, ou o texto do CSV (já decodificado pelo navegador). */
export type PlanilhaParaImportar = { xlsx: string } | { conteudo: string }

export interface TotalDoInsumo {
  nome: string
  unidade: string
  novo: boolean // não está cadastrado: a importação cadastra
  entradas: number
  saidas: number
}

export interface ResultadoImportacao {
  linhas: number
  entradas: number
  saidas: number
  insumos: TotalDoInsumo[] // na ordem da planilha
  // ↑ é onde o produtor vê um erro de escala (mil lido como um) antes de gravar
  primeira_data: string | null // AAAA-MM-DD
  ultima_data: string | null
  ja_lancadas: number // linhas iguais a movimentações já no banco: planilha repetida?
  erros: string[] // "Linha 7: ..." — com um erro sequer, nada é gravado
  importado: boolean
}

/** `GET /resumo`: a visão geral do estoque em reais. */
export interface Resumo {
  insumos: number
  valor_em_estoque: number | null // null se nenhum insumo tem custo médio
  insumos_sem_preco: number
  perdas: { ultimos_30_dias: number; total: number } // descartes e faltas da contagem
  compras_sugeridas: {
    valor: number | null // custo das reposições dos próximos 30 dias; null sem preço
    pedidos: number
    pedir_hoje: number
  }
  alertas: Record<Gravidade, number>
  talhoes_em_carencia: number
  limitacoes: string[]
}
