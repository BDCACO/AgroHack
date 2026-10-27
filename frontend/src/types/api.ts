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
  | 'carencia' // do talhão: colher antes da data é proibido

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
  // Dias entre aplicar e poder colher ou abater; 0 = não tem carência; null = não informada.
  carencia_dias: number | null
}

export interface Insumo extends InsumoCadastro {
  id: number
  demonstracao: boolean // gerado por `make demo`: não é dado real
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
  talhao_id?: number | null // onde foi aplicado, só numa saída (retirada para uso)
}

export interface Movimentacao extends MovimentacaoEntrada {
  id: number
  motivo?: 'descarte' | 'inventario' | null
  lancado_por?: string | null // nome de quem lançou, com login (auditoria); null sem login
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

export type Papel = 'dono' | 'funcionario'

export interface Usuario {
  id: number
  nome: string
  login: string
  papel: Papel
}

/** `POST /auth/entrar`: o token vem uma vez só; mande-o em `Authorization: Bearer`. */
export interface Entrada {
  token: string
  expira_em: string
  usuario: Usuario
}

export interface TalhaoCadastro {
  nome: string
  area_ha: number // maior que zero: divide o custo por hectare
  cultura: string | null
}

export interface Talhao extends TalhaoCadastro {
  id: number
  demonstracao: boolean
  colheita_liberada_em: string | null // AAAA-MM-DD; null: nada com carência aplicado
  em_carencia: boolean // colher hoje é proibido
  alertas: Alerta[] // a carência, com a conta; vazio quando liberado
  custo_total: number | null // R$ do que foi aplicado no período; null sem preço
  custo_por_ha: number | null
  limitacoes: string[]
}

export interface ConsumoNoTalhao {
  insumo_id: number
  insumo: string
  unidade: string
  quantidade: number
  custo: number | null
}

export interface TalhaoDetalhe extends Talhao {
  aplicacoes: Movimentacao[] // do período, as mais recentes primeiro
  consumo: ConsumoNoTalhao[] // por insumo, o que mais custou primeiro
}

/** Recorte de uma safra no custo e nas aplicações (a carência olha todas). AAAA-MM-DD. */
export interface Periodo {
  desde?: string
  ate?: string
}

/** `GET /usuarios`: o usuário como o dono o vê. */
export interface UsuarioCompleto extends Usuario {
  ativo: boolean
  criado_em: string
  bloqueado_ate: string | null // senhas erradas seguidas; null: não está bloqueado
}

export interface UsuarioCadastro {
  nome: string
  login: string // minúsculas, números, ponto, hífen e sublinhado
  senha: string // a inicial, de 8 ou mais; o funcionário troca depois
  papel: Papel
}

/** O que vier muda; o que não vier fica. */
export interface UsuarioAlteracao {
  nome?: string
  papel?: Papel
  ativo?: boolean
}

/** Um aparelho com login aberto. Nunca o token. */
export interface Sessao {
  id: number
  dispositivo: string | null // o que o aparelho disse ser no login: declarado, não prova
  ip: string | null
  criada_em: string
  ultimo_uso_em: string // anotado de 5 em 5 minutos
  expira_em: string
  atual: boolean // a deste navegador
}
