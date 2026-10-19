import type {
  Insumo,
  InsumoCadastro,
  InsumoDetalhe,
  Movimentacao,
  MovimentacaoEntrada,
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

/** Sem `confirmar`, a API só confere a planilha e devolve o resumo. */
export async function importarPlanilha(
  conteudo: string,
  confirmar: boolean,
): Promise<ResultadoImportacao> {
  const { data } = await http.post<ResultadoImportacao>('/importacoes', { conteudo, confirmar })
  return data
}
