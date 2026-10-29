import type { FiltroDoRelatorio, RelatorioPorPeriodo } from '@/types/api'

import { baixar } from './estoque'
import { http } from './http'

// Só o que foi preenchido: `desde=` vazio seria data inválida para a API.
const preenchidos = (filtro: FiltroDoRelatorio) =>
  Object.fromEntries(Object.entries(filtro).filter(([, valor]) => valor !== '' && valor !== undefined))

/** Sem datas, a API usa os últimos 12 meses até hoje. */
export async function buscarRelatorioPorPeriodo(filtro: FiltroDoRelatorio = {}): Promise<RelatorioPorPeriodo> {
  const { data } = await http.get<RelatorioPorPeriodo>('/relatorios/periodo', { params: preenchidos(filtro) })
  return data
}

/** O mesmo relatório, nos mesmos filtros, em arquivo: PDF para imprimir, Excel para refazer as contas. */
export const baixarRelatorioPorPeriodo = (filtro: FiltroDoRelatorio, formato: 'pdf' | 'xlsx') =>
  baixar(`/relatorios/periodo.${formato}`, `relatorio-campocerto.${formato}`, preenchidos(filtro))
