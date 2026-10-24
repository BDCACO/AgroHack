import type { Movimentacao, MovimentacaoEntrada } from '@/types/api'

import { http } from './http'

export async function listarMovimentacoes(insumoId?: string): Promise<Movimentacao[]> {
  const { data } = await http.get<Movimentacao[]>('/movimentacoes', {
    params: insumoId ? { insumo_id: insumoId } : undefined,
  })
  return data
}

export async function registrarMovimentacao(dados: MovimentacaoEntrada): Promise<Movimentacao> {
  const { data } = await http.post<Movimentacao>('/movimentacoes', dados)
  return data
}

export async function removerMovimentacao(id: string): Promise<void> {
  await http.delete(`/movimentacoes/${id}`)
}
