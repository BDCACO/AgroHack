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
  quantidade: number
  justificativa: string
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
}

export interface Insumo extends InsumoCadastro {
  id: number
  demonstracao: boolean // gerado por `make demo`: não é dado real
  estoque_atual: number
  analise: Analise
}

export interface MovimentacaoEntrada {
  insumo_id: number
  tipo: 'entrada' | 'saida'
  data: string // AAAA-MM-DD
  quantidade: number
  validade: string | null
}

export interface Movimentacao extends MovimentacaoEntrada {
  id: number
}

export interface PontoDeEstoque {
  data: string // AAAA-MM-DD
  saldo: number // no fim do dia
}

export interface InsumoDetalhe extends Insumo {
  historico: PontoDeEstoque[] // um ponto por dia com movimentação, do mais antigo
  movimentacoes: Movimentacao[] // as mais recentes primeiro
}

export interface ResultadoImportacao {
  linhas: number
  entradas: number
  saidas: number
  insumos_novos: string[]
  primeira_data: string | null // AAAA-MM-DD
  ultima_data: string | null
  ja_lancadas: number // linhas iguais a movimentações já no banco: planilha repetida?
  erros: string[] // "Linha 7: ..." — com um erro sequer, nada é gravado
  importado: boolean
}
