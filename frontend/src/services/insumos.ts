import type { Insumo, InsumoEntrada } from '@/types/api'

import { http } from './http'

export async function listarInsumos(): Promise<Insumo[]> {
  const { data } = await http.get<Insumo[]>('/insumos')
  return data
}

export async function criarInsumo(dados: InsumoEntrada): Promise<Insumo> {
  const { data } = await http.post<Insumo>('/insumos', dados)
  return data
}

export async function atualizarInsumo(id: string, dados: InsumoEntrada): Promise<Insumo> {
  const { data } = await http.put<Insumo>(`/insumos/${id}`, dados)
  return data
}

export async function removerInsumo(id: string): Promise<void> {
  await http.delete(`/insumos/${id}`)
}
