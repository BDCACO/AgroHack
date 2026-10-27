import type { Periodo, Talhao, TalhaoCadastro, TalhaoDetalhe } from '@/types/api'

import { http } from './http'

export async function listarTalhoes(): Promise<Talhao[]> {
  const { data } = await http.get<Talhao[]>('/talhoes')
  return data
}

export async function buscarTalhao(id: number, periodo: Periodo = {}): Promise<TalhaoDetalhe> {
  // Só as datas preenchidas: `desde=` vazio seria data inválida para a API.
  const params = Object.fromEntries(Object.entries(periodo).filter(([, valor]) => valor))
  const { data } = await http.get<TalhaoDetalhe>(`/talhoes/${id}`, { params })
  return data
}

export async function criarTalhao(dados: TalhaoCadastro): Promise<Talhao> {
  const { data } = await http.post<Talhao>('/talhoes', dados)
  return data
}

export async function atualizarTalhao(id: number, dados: TalhaoCadastro): Promise<Talhao> {
  const { data } = await http.put<Talhao>(`/talhoes/${id}`, dados)
  return data
}

export async function removerTalhao(id: number): Promise<void> {
  await http.delete(`/talhoes/${id}`)
}
