import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/App.vue'
import { itensDeMenu, routes } from '@/router'

// O layout verifica a API ao montar; aqui a API não existe.
vi.mock('@/services/health', () => ({
  buscarHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
  buscarReadiness: vi.fn().mockResolvedValue({ status: 'pronto', database: 'ok' }),
}))
vi.mock('@/services/estoque', () => ({
  listarInsumos: vi.fn().mockResolvedValue([]),
  listarMovimentacoes: vi.fn().mockResolvedValue([]),
}))

async function montarEm(caminho: string) {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(caminho)
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}

describe('navegação', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('o menu lista as telas na ordem das rotas', () => {
    expect(itensDeMenu.map((item) => item.rotulo)).toEqual([
      'Painel',
      'Insumos',
      'Movimentações',
      'Importar dados',
      'Sistema',
    ])
  })

  it.each([
    ['/', 'Painel'],
    ['/insumos', 'Insumos'],
    ['/movimentacoes', 'Movimentações'],
    ['/importar', 'Importar dados'],
    ['/sistema', 'Sistema'],
    ['/nao-existe', 'Página não encontrada'],
  ])('%s renderiza a página "%s"', async (caminho, titulo) => {
    const { wrapper } = await montarEm(caminho)

    expect(wrapper.find('main h1').text()).toBe(titulo)
  })

  it('o menu lateral tem um link para cada tela', async () => {
    const { wrapper } = await montarEm('/')

    const links = wrapper.findAll('nav[aria-label="Principal"] a')
    expect(links.map((link) => link.text())).toEqual(itensDeMenu.map((item) => item.rotulo))
  })

  it('a gaveta abre pelo botão e fecha ao navegar', async () => {
    const { wrapper, router } = await montarEm('/')
    const gaveta = wrapper.find('#menu-lateral')

    expect(gaveta.classes()).toContain('-translate-x-full')
    await wrapper.find('button[aria-label="Abrir menu"]').trigger('click')
    expect(gaveta.classes()).toContain('translate-x-0')

    await router.push('/insumos')
    await flushPromises()
    expect(gaveta.classes()).toContain('-translate-x-full')
  })

  it('o resumo de status do menu reflete a verificação', async () => {
    const { wrapper } = await montarEm('/')

    expect(wrapper.find('[data-teste="resumo-status"]').text()).toBe('Sistema operando')
  })
})
