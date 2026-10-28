import type { EventoDeAuditoria, FiltroDeAuditoria } from '@/types/api'

import { http } from './http'

/** Os mais recentes primeiro, uma página por vez; o total vem em X-Total-Count. */
export async function listarEventos(
  filtro: FiltroDeAuditoria,
  limite = 50,
  deslocamento = 0,
): Promise<{ eventos: EventoDeAuditoria[]; total: number }> {
  const params = Object.fromEntries(Object.entries(filtro).filter(([, valor]) => valor !== '' && valor !== undefined))
  const resposta = await http.get<EventoDeAuditoria[]>('/auditoria', {
    params: { ...params, limite, deslocamento },
  })
  const total = Number(resposta.headers['x-total-count'])
  return { eventos: resposta.data, total: Number.isFinite(total) ? total : resposta.data.length }
}
