import type { Configuracao } from '@/types/api'

import { http } from './http'

export async function buscarConfiguracao(): Promise<Configuracao> {
  const { data } = await http.get<Configuracao>('/configuracao')
  return data
}

export async function salvarConfiguracao(dados: Configuracao): Promise<Configuracao> {
  const { data } = await http.put<Configuracao>('/configuracao', dados)
  return data
}
