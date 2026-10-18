import type { HealthResponse, ReadinessResponse } from '@/types/api'

import { http } from './http'

export async function buscarHealth(): Promise<HealthResponse> {
  const { data } = await http.get<HealthResponse>('/health')
  return data
}

export async function buscarReadiness(): Promise<ReadinessResponse> {
  // 503 aqui é RESPOSTA, não falha de transporte: a API diz que o banco caiu e
  // manda o corpo explicando. Só aceita 200 e 503; o resto vira ApiError.
  const { data } = await http.get<ReadinessResponse>('/ready', {
    validateStatus: (status) => status === 200 || status === 503,
  })
  return data
}
