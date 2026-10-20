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

/** A planilha modelo (.xlsx) que a API gera, já com os insumos cadastrados. É um link
 * de download comum, não uma chamada pelo axios. */
export const URL_DA_PLANILHA_MODELO = `${http.defaults.baseURL}/importacoes/modelo.xlsx`

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
