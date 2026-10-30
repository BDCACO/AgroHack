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
  // GET /categorias. Fora do envio, a API mantém a gravada.
  categoria_id?: number | null
  // Texto livre ("Yara, Heringer"), para a mensagem de cotação. Fora do envio, a API
  // mantém o gravado.
  marcas_preferenciais?: string | null
}

export interface Insumo extends InsumoCadastro {
  id: number
  demonstracao: boolean // gerado por `make demo`: não é dado real
  estoque_atual: number
  custo_medio: number | null // R$ por unidade, das compras com preço
  valor_em_estoque: number | null // estoque atual (se positivo) × custo médio
  categoria?: string | null // o nome da categoria
  em_pedido?: number // pedido à revenda e ainda não chegou: a reposição já desconta
  chegada_prevista?: string | null // AAAA-MM-DD, a mais distante desses pedidos
  analise: Analise
}

/** O calendário de safra da fazenda inteira (não por insumo): 1 a 12, vazio enquanto
 * ninguém configurou — a análise então ignora a época do ano, como sempre ignorou. */
export interface Configuracao {
  meses_de_safra: number[]
}

export interface MovimentacaoEntrada {
  insumo_id: number
  tipo: 'entrada' | 'saida'
  data: string // AAAA-MM-DD
  quantidade: number
  validade: string | null
  valor_unitario?: number | null // R$ por unidade, só numa entrada (o preço da compra)
  talhao_id?: number | null // onde foi aplicado, só numa saída (retirada para uso)
  fornecedor_id?: number | null // de quem se comprou, só numa entrada
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

export interface FornecedorCadastro {
  nome: string
  contato: string | null // com quem falar
  telefone: string | null // o WhatsApp da revenda
  cidade: string | null
  observacao: string | null
  ativo: boolean // desativado sai das escolhas; as compras ficam
}

export interface Fornecedor extends FornecedorCadastro {
  id: number
  demonstracao: boolean
}

/** O que se pagou a um fornecedor por um insumo: é o que compara revendas. */
export interface PrecoPago {
  insumo_id: number
  insumo: string
  unidade: string
  fornecedor_id: number
  fornecedor: string
  compras: number
  quantidade: number
  preco_medio: number | null // ponderado pela quantidade; null sem preço nas compras
}

export interface FornecedorDetalhe extends Fornecedor {
  compras: Movimentacao[] // as mais recentes primeiro, até 20
  precos: PrecoPago[]
}

export type SituacaoDoPedido = 'aberto' | 'parcial' | 'recebido' | 'cancelado'

export interface ItemDoPedido {
  id: number // o que o recebimento informa
  insumo_id: number
  insumo: string
  unidade: string
  quantidade: number
  valor_unitario: number | null // o combinado com a revenda
  quantidade_recebida: number // pode passar da pedida: veio a mais
  falta_receber: number
}

export interface Pedido {
  id: number
  fornecedor_id: number | null
  fornecedor: string | null
  situacao: SituacaoDoPedido
  feito_em: string // AAAA-MM-DD
  previsto_para: string | null
  observacao: string | null
  usuario_id: number | null
  feito_por: string | null
  atrasado: boolean // a previsão passou e ainda falta chegar
  custo_estimado: number | null
  itens: ItemDoPedido[]
}

export interface PedidoEntrada {
  fornecedor_id: number | null
  feito_em?: string
  previsto_para: string | null
  observacao: string | null
  itens: { insumo_id: number; quantidade: number; valor_unitario: number | null }[]
}

/** O que chegou da carga: cada linha vira uma entrada no estoque. */
export interface Recebimento {
  data: string
  itens: {
    item_id: number
    quantidade: number
    validade: string | null
    valor_unitario: number | null // só se a nota veio com outro preço
  }[]
}

export interface ResultadoDoRecebimento {
  pedido: Pedido
  movimentacoes: Movimentacao[]
  avisos: string[] // não impedem nada: pedem para conferir
}

export interface ItemSugerido {
  insumo_id: number
  insumo: string
  unidade: string
  quantidade: number // em embalagens fechadas, já descontado o que está a caminho
  valor_unitario: number | null
  custo_estimado: number | null
  pedir_em: string
  pedir_hoje: boolean
  justificativa: string
}

/** Um pedido por revenda: a da última compra de cada insumo. */
export interface GrupoSugerido {
  fornecedor_id: number | null
  fornecedor: string | null
  itens: ItemSugerido[]
  custo_estimado: number | null
}

export interface SugestaoDePedido {
  referencia: string
  dias: number
  grupos: GrupoSugerido[]
  limitacoes: string[]
}

export type Agrupamento = 'mes' | 'semana' | 'dia'

export interface ConsumoDoInsumo {
  insumo_id: number
  insumo: string
  unidade: string
  quantidade: number // só a retirada para uso, na unidade do insumo
  valor: number | null // pelo custo médio; null sem preço
}

export interface TotalDaCategoria {
  categoria_id: number | null // null: os insumos sem categoria
  categoria: string | null
  gasto: number
  consumo: number
  perdas: number
}

export interface TotalDoFornecedor {
  fornecedor_id: number | null // null: as compras sem fornecedor
  fornecedor: string | null
  gasto: number
  compras: number
  compras_sem_preco: number
}

export interface TotaisDoPeriodo {
  consumo: ConsumoDoInsumo[]
  gasto: number // nas compras com preço
  compras_sem_preco: number // fora do gasto
  perdas: number // descarte e falta da contagem, pelo custo médio
  perdas_sem_preco: number
  por_categoria: TotalDaCategoria[]
  por_fornecedor: TotalDoFornecedor[]
}

export interface PeriodoDoRelatorio extends TotaisDoPeriodo {
  inicio: string
  fim: string
  rotulo: string // "out/2026", "semana de 19/10/2026", "24/10/2026"
}

/** `GET /relatorios/periodo`: sem movimento, o período vem zerado (sem buraco). */
export interface RelatorioPorPeriodo {
  desde: string
  ate: string
  agrupar: Agrupamento
  periodos: PeriodoDoRelatorio[]
  total: TotaisDoPeriodo
  limitacoes: string[]
}

export interface FiltroDoRelatorio {
  desde?: string
  ate?: string
  agrupar?: Agrupamento
  categoria_id?: number | ''
  insumo_id?: number | ''
  fornecedor_id?: number | ''
}

export interface Categoria {
  id: number
  nome: string
  insumos: number // com algum, ela não se remove
}

/** Os filtros de GET /movimentacoes que a tela usa. Vazio = sem filtro. */
export interface FiltroDeMovimentacoes {
  busca?: string // no nome do insumo, sem diferenciar maiúsculas nem acentos
  tipo?: 'entrada' | 'saida' | ''
  desde?: string
  ate?: string
}

/** Um registro da trilha de auditoria: só se acrescenta, nunca se apaga. */
export interface EventoDeAuditoria {
  id: number
  ocorrido_em: string
  usuario_id: number | null // null: sem login, comando no servidor ou login recusado
  feito_por: string | null
  acao: string // "usuario.criado", "login.recusado"...
  entidade: string | null
  entidade_id: number | null
  dados: Record<string, unknown> // o que foi apagado, o antes e o depois, ou o resumo
  origem: 'api' | 'terminal'
  ip: string | null
  dispositivo: string | null
}

export interface FiltroDeAuditoria {
  acao?: string // o código ou o grupo ("usuario")
  usuario_id?: number | ''
  desde?: string
  ate?: string
}
