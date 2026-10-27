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
      'Talhões',
      'Importar dados',
      'Usuários',
      'Sistema',
    ])
  })

  it.each([
    ['/', 'Painel'],
    ['/insumos', 'Insumos'],
    ['/movimentacoes', 'Movimentações'],
    ['/talhoes', 'Talhões'],
    ['/importar', 'Importar dados'],
    ['/sistema', 'Sistema'],
    ['/nao-existe', 'Página não encontrada'],
  ])('%s renderiza a página "%s"', async (caminho, titulo) => {
    const { wrapper } = await montarEm(caminho)

    expect(wrapper.find('main h1').text()).toBe(titulo)
  })

  it('o menu lateral tem um link para cada tela', async () => {
    const { wrapper } = await montarEm('/')

    const links = wrapper.findAll('aside nav a')
    // Sem login, as telas que dependem dele (Usuários) ficam fora.
    expect(links.map((link) => link.text())).toEqual(
      itensDeMenu.filter((item) => !item.comLogin).map((item) => item.rotulo),
    )
  })

  it('no celular, a barra de baixo tem as telas do dia a dia, com rótulos que cabem nela', async () => {
    const { wrapper } = await montarEm('/movimentacoes')

    const abas = wrapper.findAll('[data-teste="aba"]')
    expect(abas.map((aba) => aba.text())).toEqual(
      itensDeMenu.filter((item) => item.barra).map((item) => item.rotuloCurto),
    )
    expect(abas.map((aba) => aba.text())).toContain('Movimentos')
    expect(abas.map((aba) => aba.attributes('aria-current'))).toContain('page')
    expect(wrapper.find('[data-teste="aba-mais"]').text()).toBe('Mais')
  })

  it('o "Mais" do celular abre as outras telas, e acende quando se está numa delas', async () => {
    const { wrapper } = await montarEm('/sistema', { attachTo: document.body })
    expect(wrapper.find('[data-teste="aba-mais"]').classes()).toContain('text-white')

    await wrapper.find('[data-teste="aba-mais"]').trigger('click')
    const outras = [...document.querySelectorAll('[data-teste="menu-mais"] a')].map((a) => a.textContent?.trim())
    expect(outras).toEqual(itensDeMenu.filter((item) => !item.barra && !item.comLogin).map((item) => item.rotulo))
    expect(outras).toContain('Sistema')
    wrapper.unmount()
  })

  it('a aba do Painel mostra quantos alertas urgentes há', async () => {
    const urgente: Insumo = {
      id: 1,
      nome: 'Ureia agrícola',
      unidade: 'kg',
      estoque_minimo: 300,
      prazo_reposicao_dias: 10,
      embalagem: null,
      pedido_minimo: null,
      carencia_dias: null,
      custo_medio: null,
      valor_em_estoque: null,
      demonstracao: false,
      estoque_atual: 100,
      analise: {
        consumo_diario: null,
        cobertura_dias: null,
        alertas: [{ tipo: 'abaixo_do_minimo', gravidade: 'alta', justificativa: 'Abaixo do mínimo.' }],
        reposicao: null,
        limitacoes: [],
      },
    }
    vi.mocked(listarInsumos).mockResolvedValueOnce([urgente])
    const { wrapper } = await montarEm('/insumos')

    expect(wrapper.find('[data-teste="urgentes-aba"]').text()).toBe('1 urgente')
  })

  it('tocar de novo na aba da tela atual sobe para o topo, sem navegar', async () => {
    const { wrapper, router } = await montarEm('/insumos')
    const subir = vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
    const empurrar = vi.spyOn(router, 'push')

    await wrapper.findAll('[data-teste="aba"]')[1]!.trigger('click')

    expect(subir).toHaveBeenCalledWith(expect.objectContaining({ top: 0 }))
    expect(empurrar).not.toHaveBeenCalled()
    subir.mockRestore()
  })

  it('na página de um insumo, a aba Insumos acende e leva de volta à lista', async () => {
    const { wrapper, router } = await montarEm('/insumos/7')
    const insumos = wrapper.findAll('[data-teste="aba"]')[1]!
    expect(insumos.attributes('aria-current')).toBe('page')

    await insumos.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('insumos')
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
      embalagem: null,
      pedido_minimo: null,
      carencia_dias: null,
      custo_medio: null,
      valor_em_estoque: null,
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
