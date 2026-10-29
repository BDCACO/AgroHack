import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import ConfiguracoesPage from '@/pages/ConfiguracoesPage.vue'
import { routes } from '@/router'
import * as api from '@/services/configuracao'
import { useSessaoStore } from '@/stores/sessao'
import type { Usuario } from '@/types/api'

vi.mock('@/services/configuracao', () => ({
  buscarConfiguracao: vi.fn(),
  salvarConfiguracao: vi.fn(),
}))
vi.mock('@/services/health', () => ({
  buscarHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
  buscarReadiness: vi.fn().mockResolvedValue({ status: 'pronto', database: 'ok' }),
}))

const FUNCIONARIO: Usuario = { id: 2, nome: 'Zé', login: 'ze', papel: 'funcionario' }

async function montar() {
  const router = createRouter({ history: createMemoryHistory(), routes })
  const wrapper = mount(ConfiguracoesPage, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

// O Sistema virou parte de Configurações, e o calendário foi junto.
describe('Calendário de safra, em Configurações', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.buscarConfiguracao).mockResolvedValue({ meses_de_safra: [] })
  })

  it('o dono vê o calendário e salva os meses escolhidos', async () => {
    vi.mocked(api.salvarConfiguracao).mockResolvedValue({ meses_de_safra: [9] })
    const wrapper = await montar()

    const secao = wrapper.find('[data-teste="calendario-de-safra"]')
    expect(secao.exists()).toBe(true)
    await secao.findAll('button').find((b) => b.text() === 'Set')!.trigger('click')
    await secao.find('button[type="submit"], [data-teste="salvar-calendario"]').trigger('click')
    await flushPromises()

    expect(api.salvarConfiguracao).toHaveBeenCalledWith({ meses_de_safra: [9] })
  })

  it('o funcionário não vê o calendário', async () => {
    useSessaoStore().usuario = FUNCIONARIO

    const wrapper = await montar()

    expect(wrapper.find('[data-teste="calendario-de-safra"]').exists()).toBe(false)
  })
})
