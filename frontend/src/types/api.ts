// Espelho dos schemas Pydantic de backend/app/schemas/. Escrito à mão enquanto a
// API tem dois endpoints; quando crescer, gerar a partir do OpenAPI (como faz o
// ArkoHub) — ver docs/ARQUITETURA.md, "Próximas decisões".

export interface HealthResponse {
  status: 'ok'
}

export interface ReadinessResponse {
  status: 'pronto' | 'indisponivel'
  database: 'ok' | 'erro'
}
