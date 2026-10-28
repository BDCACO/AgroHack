import type { FiltroDoRelatorio, RelatorioPorPeriodo } from '@/types/api'

import { http } from './http'

/** Sem datas, a API usa os últimos 12 meses até hoje. */
export async function buscarRelatorioPorPeriodo(filtro: FiltroDoRelatorio = {}): Promise<RelatorioPorPeriodo> {
  // Só o que foi preenchido: `desde=` vazio seria data inválida para a API.
  const params = Object.fromEntries(Object.entries(filtro).filter(([, valor]) => valor !== '' && valor !== undefined))
  const { data } = await http.get<RelatorioPorPeriodo>('/relatorios/periodo', { params })
  return data
}
