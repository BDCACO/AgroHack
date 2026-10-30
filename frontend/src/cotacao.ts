import { dataBr } from './formatos'
import type { Insumo, Reposicao } from './types/api'

export type ItemDeReposicao = Reposicao & { insumo: Insumo }

function linhaDoItem(item: ItemDeReposicao): string {
  const { insumo } = item
  const quantidade = `${item.quantidade.toLocaleString('pt-BR')} ${insumo.unidade}`
  // As embalagens e o prazo vêm da API, com o mesmo arredondamento da justificativa e
  // a data de Rondônia: a mensagem não refaz a conta com o relógio do navegador.
  const embalagens =
    item.embalagens != null && insumo.embalagem
      ? ` (${item.embalagens} ${item.embalagens === 1 ? 'embalagem' : 'embalagens'} de ` +
        `${insumo.embalagem.toLocaleString('pt-BR')} ${insumo.unidade})`
      : ''
  const marca = insumo.marcas_preferenciais
    ? `Marca: ${insumo.marcas_preferenciais}`
    : 'Qualquer marca/similar equivalente'
  return `- ${insumo.nome}: ${quantidade}${embalagens} · ${marca} · Entregar até ${dataBr(item.entregar_ate)}`
}

/** O pedido à revenda, pronto em texto, para mandar pelo WhatsApp: o que pedir agora
 * separado do que ainda dá para esperar, cada item com marca de preferência (ou
 * "qualquer uma") e até quando o estoque aguenta. */
export function mensagemDeCotacao(itens: ItemDeReposicao[], hoje: Date): string {
  const agora = itens.filter((item) => item.pedir_hoje)
  const depois = itens.filter((item) => !item.pedir_hoje)
  return [
    `Lista de compras (CampoCerto, ${hoje.toLocaleDateString('pt-BR')})`,
    ...(agora.length ? ['', 'Pedir agora:', ...agora.map(linhaDoItem)] : []),
    ...(depois.length
      ? [
          '',
          'Próximos pedidos:',
          ...depois.map((item) => `${linhaDoItem(item)} · pedir até ${dataBr(item.pedir_em)}`),
        ]
      : []),
  ].join('\n')
}
