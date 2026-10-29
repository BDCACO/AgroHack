// Os `dados` de um registro da trilha em palavras, para quem não lê JSON: "Situação antes:
// A caminho", e não `situacao_antes: aberto`. Campo que a tela ainda não conhece aparece com
// o nome arrumado ("prazo_novo" vira "Prazo novo") e o valor como veio: nada se perde.
import { dataBr, dataHora, reais } from '@/formatos'

export interface LinhaLegivel {
  rotulo: string
  valor?: string
  filhos?: LinhaLegivel[]
}

const CAMPOS: Record<string, string> = {
  nome: 'Nome',
  login: 'Login',
  papel: 'Papel',
  ativo: 'Ativo',
  motivo: 'Motivo',
  ate: 'Até',
  bloqueado_ate: 'Bloqueado até',
  desfez_bloqueio: 'Desfez o bloqueio',
  limite: 'Limite de tentativas',
  janela_segundos: 'Janela',
  liberado_em: 'Liberado em',
  sessoes: 'Aparelhos',
  dispositivo: 'Aparelho',
  ip: 'IP',
  criada_em: 'Entrou em',
  aberta_em: 'Entrou em',
  ultimo_uso: 'Último uso',
  insumo: 'Insumo',
  unidade: 'Unidade',
  categoria: 'Categoria',
  categoria_id: 'Categoria nº',
  estoque_minimo: 'Estoque mínimo',
  prazo_reposicao_dias: 'Prazo de entrega (dias)',
  embalagem: 'Embalagem',
  pedido_minimo: 'Pedido mínimo',
  carencia_dias: 'Carência (dias)',
  tipo: 'Tipo',
  data: 'Data',
  quantidade: 'Quantidade',
  validade: 'Validade',
  valor_unitario: 'Preço unitário',
  talhao: 'Talhão',
  area_ha: 'Área (ha)',
  cultura: 'Cultura',
  fornecedor: 'Fornecedor',
  cidade: 'Cidade',
  telefone: 'Telefone',
  feito_em: 'Pedido em',
  previsto_para: 'Previsão de chegada',
  situacao_antes: 'Situação antes',
  situacao: 'Situação',
  observacao: 'Observação',
  itens: 'Itens',
  quantidade_recebida: 'Já tinha chegado',
  falta_receber: 'Faltava chegar',
  lancado_por: 'Lançado por',
  movimentacoes: 'Movimentações',
  pedidos: 'Pedidos',
  formato: 'Formato',
  linhas: 'Linhas',
  entradas: 'Entradas',
  saidas: 'Saídas',
  primeira_data: 'Primeira data',
  ultima_data: 'Última data',
  ja_lancadas: 'Já estavam lançadas',
  insumos: 'Insumos',
  fornecedores: 'Fornecedores',
  talhoes: 'Talhões',
  fornecedores_novos: 'Fornecedores novos',
  categorias_novas: 'Categorias novas',
  criados: 'Criados',
  removidos: 'Removidos',
  referencia: 'Data de referência',
}

const VALORES: Record<string, Record<string, string>> = {
  papel: { dono: 'Dono', funcionario: 'Funcionário' },
  motivo: {
    senha_incorreta: 'Senha incorreta',
    bloqueado: 'Login bloqueado',
    usuario_desativado: 'Usuário desativado',
    senha_atual_incorreta: 'Senha atual incorreta',
    descarte: 'Descarte',
    inventario: 'Contagem do galpão',
  },
  situacao_antes: { aberto: 'A caminho', parcial: 'Chegou parte', recebido: 'Recebido', cancelado: 'Cancelado' },
  situacao: { aberto: 'A caminho', parcial: 'Chegou parte', recebido: 'Recebido', cancelado: 'Cancelado' },
  tipo: { entrada: 'Entrada', saida: 'Saída' },
  formato: { xlsx: 'Excel', csv: 'CSV' },
}
// Em reais, e não um número solto.
const DINHEIRO = new Set(['valor_unitario', 'valor', 'gasto', 'custo', 'preco'])
// Só para quem vai cruzar com o banco: na leitura fácil, ficam de fora.
const TECNICOS = new Set(['uuid', 'item_do_pedido_id'])

/** "prazo_novo" vira "Prazo novo". */
const humanizar = (chave: string) => {
  const texto = chave.replaceAll('_', ' ').trim()
  return texto.charAt(0).toUpperCase() + texto.slice(1)
}
export const rotuloDoCampo = (chave: string) => CAMPOS[chave] ?? humanizar(chave)

export function valorLegivel(chave: string, valor: unknown): string {
  if (valor === null || valor === undefined || valor === '') return '—'
  if (typeof valor === 'boolean') return valor ? 'Sim' : 'Não'
  if (typeof valor === 'number') {
    if (DINHEIRO.has(chave)) return reais(valor)
    if (chave === 'janela_segundos') return valor >= 3600 ? `${valor / 3600} h` : `${valor / 60} min`
    return valor.toLocaleString('pt-BR', { maximumFractionDigits: 3 })
  }
  if (typeof valor === 'string') {
    const traduzido = VALORES[chave]?.[valor]
    if (traduzido) return traduzido
    if (/^\d{4}-\d{2}-\d{2}$/.test(valor)) return dataBr(valor)
    if (/^\d{4}-\d{2}-\d{2}T/.test(valor)) return dataHora(valor)
    return valor
  }
  if (Array.isArray(valor)) return valor.map((item) => valorLegivel(chave, item)).join(', ')
  return JSON.stringify(valor)
}

const ehObjeto = (valor: unknown): valor is Record<string, unknown> =>
  typeof valor === 'object' && valor !== null && !Array.isArray(valor)

/** O nome que identifica um item da lista: o insumo da linha, o nome, o login, o aparelho. */
function tituloDoItem(item: Record<string, unknown>, indice: number): { titulo: string; chave?: string } {
  for (const chave of ['insumo', 'nome', 'login', 'dispositivo']) {
    if (typeof item[chave] === 'string' && item[chave]) return { titulo: item[chave] as string, chave }
  }
  return { titulo: `${indice + 1}º` }
}

export function dadosLegiveis(dados: Record<string, unknown>, esconder: string[] = []): LinhaLegivel[] {
  const linhas: LinhaLegivel[] = []
  // A alteração: só o que mudou, de quanto para quanto.
  if (ehObjeto(dados.antes) && ehObjeto(dados.depois)) {
    const antes = dados.antes
    const depois = dados.depois
    linhas.push({
      rotulo: 'O que mudou',
      filhos: Object.keys(depois).map((campo) => ({
        rotulo: rotuloDoCampo(campo),
        valor: `${valorLegivel(campo, antes[campo])} → ${valorLegivel(campo, depois[campo])}`,
      })),
    })
  }
  for (const [chave, valor] of Object.entries(dados)) {
    if (chave === 'antes' || chave === 'depois' || esconder.includes(chave) || TECNICOS.has(chave)) continue
    // "fornecedor_id: 3" ao lado de "fornecedor: AgroVet" não diz nada a mais.
    if (chave.endsWith('_id') && typeof dados[chave.slice(0, -3)] === 'string') continue
    if (ehObjeto(valor)) {
      linhas.push({ rotulo: rotuloDoCampo(chave), filhos: dadosLegiveis(valor) })
    } else if (Array.isArray(valor) && valor.some(ehObjeto)) {
      linhas.push({
        rotulo: rotuloDoCampo(chave),
        filhos: valor.map((item, indice) => {
          if (!ehObjeto(item)) return { rotulo: `${indice + 1}º`, valor: valorLegivel(chave, item) }
          // O que dá nome ao item vira o título dele, e não se repete dentro.
          const { titulo, chave: doTitulo } = tituloDoItem(item, indice)
          return { rotulo: titulo, filhos: dadosLegiveis(item, doTitulo ? [doTitulo] : []) }
        }),
      })
    } else {
      linhas.push({ rotulo: rotuloDoCampo(chave), valor: valorLegivel(chave, valor) })
    }
  }
  return linhas
}
