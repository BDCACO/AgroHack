import type {
  Insumo,
  InsumoCadastro,
  Movimentacao,
  MovimentacaoEntrada,
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
