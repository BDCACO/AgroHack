import { dataBr } from './formatos'
import type { Insumo, Reposicao } from './types/api'

export type ItemDeReposicao = Reposicao & { insumo: Insumo }

function linhaDoItem(item: ItemDeReposicao, hoje: Date): string {
  const { insumo } = item
  const quantidade = `${item.quantidade.toLocaleString('pt-BR')} ${insumo.unidade}`
  const embalagens = insumo.embalagem
    ? ` (${Math.ceil(item.quantidade / insumo.embalagem)} embalagens de ` +
      `${insumo.embalagem.toLocaleString('pt-BR')} ${insumo.unidade})`
    : ''
  const marca = insumo.marcas_preferenciais
    ? `Marca: ${insumo.marcas_preferenciais}`
    : 'Qualquer marca/similar equivalente'
  const cobertura = insumo.analise.cobertura_dias
  const entrega =
    cobertura == null
      ? ''
      : ` · Entregar até ${new Date(hoje.getTime() + cobertura * 86_400_000).toLocaleDateString('pt-BR')}`
  return `- ${insumo.nome}: ${quantidade}${embalagens} · ${marca}${entrega}`
}

/** O pedido à revenda, pronto em texto, para mandar pelo WhatsApp: o que pedir agora
 * separado do que ainda dá para esperar, cada item com marca de preferência (ou
 * "qualquer uma") e até quando o estoque aguenta. */
export function mensagemDeCotacao(itens: ItemDeReposicao[], hoje: Date): string {
  const agora = itens.filter((item) => item.pedir_hoje)
  const depois = itens.filter((item) => !item.pedir_hoje)
  return [
    `Lista de compras (CampoCerto, ${hoje.toLocaleDateString('pt-BR')})`,
    ...(agora.length ? ['', 'Pedir agora:', ...agora.map((item) => linhaDoItem(item, hoje))] : []),
    ...(depois.length
      ? [
          '',
          'Próximos pedidos:',
          ...depois.map((item) => `${linhaDoItem(item, hoje)} · pedir até ${dataBr(item.pedir_em)}`),
        ]
      : []),
  ].join('\n')
}
