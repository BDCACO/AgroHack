import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/App.vue'
import { itensDeMenu, routes } from '@/router'
import { listarInsumos } from '@/services/estoque'
import type { Insumo } from '@/types/api'

// O layout verifica a API ao montar; aqui a API não existe.
// Movimentações carrega os fornecedores para a compra.
vi.mock('@/services/compras', () => ({ listarFornecedores: vi.fn().mockResolvedValue([]) }))
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
      'Compras',
      'Talhões',
      'Relatórios',
      'Importar dados',
      'Usuários',
      'Auditoria',
      'Configurações',
    ])
  })

  it.each([
    ['/', 'Painel'],
    ['/insumos', 'Insumos'],
    ['/movimentacoes', 'Movimentações'],
    ['/talhoes', 'Talhões'],
    ['/importar', 'Importar dados'],
    ['/configuracoes', 'Configurações'],
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

  it('o botão da barra do topo recolhe o menu aos ícones, e o navegador lembra', async () => {
    localStorage.clear()
    const { wrapper } = await montarEm('/')
    const botao = wrapper.find('[data-teste="recolher-menu"]')
    expect(botao.attributes('aria-expanded')).toBe('true')
    expect(botao.attributes('aria-label')).toBe('Recolher o menu')

    await botao.trigger('click')

    expect(wrapper.find('aside').attributes('data-recolhido')).toBe('true')
    expect(botao.attributes('aria-expanded')).toBe('false')
    expect(botao.attributes('aria-label')).toBe('Abrir o menu')
    // O nome de cada tela some da vista, mas continua para o leitor de tela e no "title".
    const insumos = wrapper.findAll('aside nav a')[1]!
    expect(insumos.text()).toBe('Insumos')
    expect(insumos.find('[data-teste="rotulo-menu"]').classes()).toContain('sr-only')
    expect(insumos.attributes('title')).toBe('Insumos')
    expect(localStorage.getItem('campocerto.menu-recolhido')).toBe('1')
    wrapper.unmount()

    setActivePinia(createPinia())
    const outra = await montarEm('/insumos')
    expect(outra.wrapper.find('aside').attributes('data-recolhido')).toBe('true')
    await outra.wrapper.find('[data-teste="recolher-menu"]').trigger('click')
    expect(outra.wrapper.find('aside').attributes('data-recolhido')).toBeUndefined()
    expect(localStorage.getItem('campocerto.menu-recolhido')).toBe('0')
    localStorage.clear()
  })

  it('a barra do topo diz onde se está, com a volta para a seção numa página dentro dela', async () => {
    const naSecao = await montarEm('/insumos')
    expect(naSecao.wrapper.find('[data-teste="barra-do-topo"] nav').text()).toBe('Insumos')
    // O título fica só na barra (e no cabeçalho do celular); o h1 da página, para o leitor de tela.
    expect(naSecao.wrapper.find('main h1').classes()).toContain('sr-only')
    expect(naSecao.wrapper.find('[data-teste="titulo-celular"]').text()).toBe('Insumos')

    setActivePinia(createPinia())
    const dentro = await montarEm('/compras/fornecedores')
    const caminho = dentro.wrapper.find('[data-teste="barra-do-topo"] nav')
    expect(caminho.findAll('li').map((li) => li.text())).toEqual(['Compras', 'Fornecedores'])
    expect(caminho.find('a').attributes('href')).toBe('/compras')
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
    const { wrapper } = await montarEm('/configuracoes', { attachTo: document.body })
    expect(wrapper.find('[data-teste="aba-mais"]').classes()).toContain('text-white')

    await wrapper.find('[data-teste="aba-mais"]').trigger('click')
    const outras = [...document.querySelectorAll('[data-teste="menu-mais"] a')].map((a) => a.textContent?.trim())
    expect(outras).toEqual(itensDeMenu.filter((item) => !item.barra && !item.comLogin).map((item) => item.rotulo))
    expect(outras).toContain('Configurações')
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

  it('a barra do topo leva ao código do projeto no GitHub, em outra aba', async () => {
    const { wrapper } = await montarEm('/')

    const link = wrapper.find('[data-teste="link-github"]')
    expect(link.attributes('href')).toBe('https://github.com/BDCACO/AgroHack')
    expect(link.attributes('target')).toBe('_blank')
    expect(link.attributes('rel')).toContain('noopener')
  })
})
