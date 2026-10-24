// Espelho dos schemas Pydantic de backend/app/schemas/. Escrito à mão enquanto a
// API é pequena; quando crescer, gerar a partir do OpenAPI (como faz o
// ArkoHub) — ver docs/ARQUITETURA.md, "Próximas decisões".

export interface HealthResponse {
  status: 'ok'
}

export interface ReadinessResponse {
  status: 'pronto' | 'indisponivel'
  database: 'ok' | 'erro'
}

/** Corpo de erro de regra de negócio (404/409). */
export interface ErroDeNegocio {
  codigo: string
  mensagem: string
}

export interface InsumoEntrada {
  nome: string
  categoria: string | null
  unidade: string
  estoque_minimo: number
}

export interface Insumo extends InsumoEntrada {
  id: string
  /** Calculado pela API a partir das movimentações. */
  saldo_atual: number
  criado_em: string
}

export type TipoMovimentacao = 'compra' | 'retirada'

export interface MovimentacaoEntrada {
  insumo_id: string
  tipo: TipoMovimentacao
  quantidade: number
  /** AAAA-MM-DD */
  data: string
  /** AAAA-MM-DD; só em compra. */
  validade: string | null
  observacao: string | null
}

export interface Movimentacao extends MovimentacaoEntrada {
  id: string
  insumo_nome: string
  insumo_unidade: string
  criado_em: string
}
