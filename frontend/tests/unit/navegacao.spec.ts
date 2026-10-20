import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/App.vue'
import { itensDeMenu, routes } from '@/router'
import { listarInsumos } from '@/services/estoque'
import type { Insumo } from '@/types/api'

// O layout verifica a API ao montar; aqui a API não existe.
vi.mock('@/services/health', () => ({
  buscarHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
  buscarReadiness: vi.fn().mockResolvedValue({ status: 'pronto', database: 'ok' }),
}))
vi.mock('@/services/estoque', async (original) => ({
  ...(await original<typeof import('@/services/estoque')>()),
  listarInsumos: vi.fn().mockResolvedValue([]),
  listarMovimentacoes: vi.fn().mockResolvedValue([]),
}))

async function montarEm(caminho: string, opcoes: { attachTo?: HTMLElement } = {}) {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(caminho)
  await router.isReady()
  // attachTo: só montado no documento o foco existe de verdade.
  const wrapper = mount(App, { global: { plugins: [router] }, ...opcoes })
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

  it('fechada no celular, a gaveta sai do Tab; aberta, o resto da tela fica inerte', async () => {
    const { wrapper } = await montarEm('/')
    const gaveta = wrapper.find('#menu-lateral')
    const conteudo = wrapper.find('main').element.parentElement!

    expect(gaveta.classes()).toContain('max-lg:invisible')
    await wrapper.find('button[aria-label="Abrir menu"]').trigger('click')

    expect(gaveta.classes()).not.toContain('max-lg:invisible')
    expect(conteudo.hasAttribute('inert')).toBe(true)
  })

  it('Esc fecha a gaveta e devolve o foco ao botão que a abriu', async () => {
    const { wrapper } = await montarEm('/', { attachTo: document.body })
    const abrir = wrapper.find('button[aria-label="Abrir menu"]')
    await abrir.trigger('click')
    await flushPromises()
    expect(document.activeElement?.getAttribute('aria-label')).toBe('Fechar menu')

    await wrapper.find('#menu-lateral').trigger('keydown', { key: 'Escape' })

    expect(wrapper.find('#menu-lateral').classes()).toContain('-translate-x-full')
    expect(document.activeElement).toBe(abrir.element)
    wrapper.unmount()
  })

  it('ao trocar de página, o foco vai para o conteúdo novo', async () => {
    const { wrapper, router } = await montarEm('/', { attachTo: document.body })

    await router.push('/insumos')
    await flushPromises()

    expect(document.activeElement?.id).toBe('conteudo')
    // E quem chega pelo teclado pode pular o menu desde o primeiro Tab.
    expect(wrapper.find('a[href="#conteudo"]').text()).toBe('Pular para o conteúdo')
    wrapper.unmount()
  })

  it('o resumo de status do menu reflete a verificação', async () => {
    const { wrapper } = await montarEm('/')

    expect(wrapper.find('[data-teste="resumo-status"]').text()).toBe('Sistema operando')
  })

  it('avisa quando há dados de demonstração, e só nesse caso', async () => {
    const semDemo = await montarEm('/')
    expect(semDemo.wrapper.find('[data-teste="aviso-demonstracao"]').exists()).toBe(false)

    const insumoDeDemo: Insumo = {
      id: 1,
      nome: 'Ureia agrícola',
      unidade: 'kg',
      estoque_minimo: null,
      prazo_reposicao_dias: null,
      demonstracao: true,
      estoque_atual: 0,
      analise: {
        consumo_diario: null,
        cobertura_dias: null,
        alertas: [],
        reposicao: null,
        limitacoes: [],
      },
    }
    vi.mocked(listarInsumos).mockResolvedValueOnce([insumoDeDemo])
    const comDemo = await montarEm('/insumos')

    expect(comDemo.wrapper.find('[data-teste="aviso-demonstracao"]').exists()).toBe(true)
  })
})
