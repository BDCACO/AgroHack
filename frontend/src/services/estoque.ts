import type {
  Insumo,
  InsumoCadastro,
  InsumoDetalhe,
  Movimentacao,
  MovimentacaoEntrada,
  PlanilhaParaImportar,
  ResultadoImportacao,
} from '@/types/api'

import { http } from './http'

export async function listarInsumos(): Promise<Insumo[]> {
  const { data } = await http.get<Insumo[]>('/insumos')
  return data
}

export async function criarInsumo(dados: InsumoCadastro): Promise<Insumo> {
  const { data } = await http.post<Insumo>('/insumos', dados)
  return data
}

export async function atualizarInsumo(id: number, dados: InsumoCadastro): Promise<Insumo> {
  const { data } = await http.put<Insumo>(`/insumos/${id}`, dados)
  return data
}

export async function buscarInsumo(id: number): Promise<InsumoDetalhe> {
  const { data } = await http.get<InsumoDetalhe>(`/insumos/${id}`)
  return data
}

export async function removerInsumo(id: number): Promise<void> {
  await http.delete(`/insumos/${id}`)
}

export async function listarMovimentacoes(): Promise<Movimentacao[]> {
  const { data } = await http.get<Movimentacao[]>('/movimentacoes')
  return data
}

export async function registrarMovimentacao(dados: MovimentacaoEntrada): Promise<Movimentacao> {
  const { data } = await http.post<Movimentacao>('/movimentacoes', dados)
  return data
}

export async function removerMovimentacao(id: number): Promise<void> {
  await http.delete(`/movimentacoes/${id}`)
}

/** Baixa um arquivo que a API gera. Pelo cliente HTTP, e não por um link comum: o link não
 * levaria o token da sessão. O nome vem da API (Content-Disposition). */
async function baixar(caminho: string, nomePadrao: string): Promise<void> {
  const resposta = await http.get<Blob>(caminho, { responseType: 'blob', timeout: 60_000 })
  const disposicao = String(resposta.headers['content-disposition'] ?? '')
  const nome = /filename="([^"]+)"/.exec(disposicao)?.[1] ?? nomePadrao
  const url = URL.createObjectURL(resposta.data)
  const link = Object.assign(document.createElement('a'), { href: url, download: nome })
  document.body.append(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

/** A planilha modelo (.xlsx) que a API gera, já com os insumos cadastrados. */
export const baixarPlanilhaModelo = () =>
  baixar('/importacoes/modelo.xlsx', 'modelo-campocerto.xlsx')

/** Relatório do estoque (.xlsx): alertas, reposição, insumos e todas as movimentações. */
export const baixarRelatorio = () => baixar('/relatorio.xlsx', 'relatorio-campocerto.xlsx')

/** Sem `confirmar`, a API só confere a planilha e devolve o resumo. */
export async function importarPlanilha(
  planilha: PlanilhaParaImportar,
  confirmar: boolean,
): Promise<ResultadoImportacao> {
  // Planilha grande demora mais que os 10 s padrão. E, no confirmar, desistir antes do
  // servidor terminar é pior que esperar: ele grava assim mesmo.
  const { data } = await http.post<ResultadoImportacao>(
    '/importacoes',
    { ...planilha, confirmar },
    { timeout: 120_000 },
  )
  return data
}
