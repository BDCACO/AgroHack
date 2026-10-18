import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { buscarHealth, buscarReadiness } from '@/services/health'
import { ApiError } from '@/services/http'
import { useStatusSistemaStore } from '@/stores/statusSistema'

vi.mock('@/services/health', () => ({
  buscarHealth: vi.fn(),
  buscarReadiness: vi.fn(),
}))

describe('useStatusSistemaStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  it('marca API e banco como ok quando os dois respondem', async () => {
    vi.mocked(buscarHealth).mockResolvedValue({ status: 'ok' })
    vi.mocked(buscarReadiness).mockResolvedValue({ status: 'pronto', database: 'ok' })
    const store = useStatusSistemaStore()

    await store.verificar()

    expect(store.api).toBe('ok')
    expect(store.banco).toBe('ok')
    expect(store.verificando).toBe(false)
    expect(store.verificadoEm).toBeInstanceOf(Date)
  })

  it('marca o banco como erro quando /ready responde indisponível', async () => {
    vi.mocked(buscarHealth).mockResolvedValue({ status: 'ok' })
    vi.mocked(buscarReadiness).mockResolvedValue({ status: 'indisponivel', database: 'erro' })
    const store = useStatusSistemaStore()

    await store.verificar()

    expect(store.api).toBe('ok')
    expect(store.banco).toBe('erro')
  })

  it('não afirma nada sobre o banco quando a API está fora do ar', async () => {
    vi.mocked(buscarHealth).mockRejectedValue(new ApiError(null))
    const store = useStatusSistemaStore()
    store.banco = 'ok' // resultado de uma verificação anterior

    await store.verificar()

    expect(store.api).toBe('erro')
    expect(store.banco).toBe('desconhecido')
    expect(buscarReadiness).not.toHaveBeenCalled()
  })
})
