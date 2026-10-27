import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/App.vue'
import { routes } from '@/router'
import * as categorias from '@/services/categorias'
import * as estoque from '@/services/estoque'
import { ApiError } from '@/services/http'
import type { Insumo, Movimentacao } from '@/types/api'

vi.mock('@/services/health', () => ({
  buscarHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
  buscarReadiness: vi.fn().mockResolvedValue({ status: 'pronto', database: 'ok' }),
}))
vi.mock('@/services/estoque', async (original) => ({
  ...(await original<typeof import('@/services/estoque')>()),
  listarInsumos: vi.fn(),
  listarMovimentacoes: vi.fn(),
  buscarMovimentacoes: vi.fn(),
  criarInsumo: vi.fn(),
  atualizarInsumo: vi.fn(),
  buscarResumo: vi.fn().mockRejectedValue(new Error('sem resumo aqui')),
}))
vi.mock('@/services/categorias', () => ({
  listarCategorias: vi.fn(),
  criarCategoria: vi.fn(),
  renomearCategoria: vi.fn(),
  removerCategoria: vi.fn(),
}))
vi.mock('@/services/compras', () => ({ listarFornecedores: vi.fn().mockResolvedValue([]) }))
vi.mock('@/services/talhoes', () => ({ listarTalhoes: vi.fn().mockResolvedValue([]) }))

function insumo(id: number, nome: string, mudancas: Partial<Insumo> = {}): Insumo {
  return {
    id,
    nome,
    unidade: 'kg',
    estoque_minimo: null,
    prazo_reposicao_dias: null,
    embalagem: null,
    pedido_minimo: null,
    carencia_dias: null,
    custo_medio: null,
    valor_em_estoque: null,
    demonstracao: false,
    estoque_atual: 100,
    categoria_id: null,
    categoria: null,
    em_pedido: 0,
    chegada_prevista: null,
    analise: { consumo_diario: null, cobertura_dias: null, alertas: [], reposicao: null, limitacoes: [] },
    ...mudancas,
  }
}
const alerta = (gravidade: 'alta' | 'media') => ({
  consumo_diario: null,
  cobertura_dias: null,
  alertas: [{ tipo: 'abaixo_do_minimo' as const, gravidade, justificativa: 'x' }],
  reposicao: null,
  limitacoes: [],
})
const ureia = insumo(1, 'Uréia agrícola', {
  categoria_id: 10,
  categoria: 'Fertilizante',
  analise: alerta('alta'),
  em_pedido: 700,
  chegada_prevista: '2026-11-05',
})
const sal = insumo(2, 'Sal mineral 80P', { categoria_id: 11, categoria: 'Nutrição animal', analise: alerta('media') })
const calcario = insumo(3, 'Calcário dolomítico')

const mov = (id: number, tipo: 'entrada' | 'saida'): Movimentacao => ({
  id,
  insumo_id: 1,
  tipo,
  data: '2026-10-20',
  quantidade: id,
  validade: null,
})

async function montarEm(caminho: string) {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(caminho)
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return wrapper
}
const nomes = (wrapper: ReturnType<typeof mount>) =>
  wrapper.findAll('[data-teste="insumo-celular"] a').map((a) => a.text())

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  document.body.innerHTML = ''
  vi.mocked(estoque.listarInsumos).mockResolvedValue([calcario, sal, ureia])
  vi.mocked(estoque.listarMovimentacoes).mockResolvedValue([mov(1, 'entrada'), mov(2, 'saida')])
  vi.mocked(categorias.listarCategorias).mockResolvedValue([
    { id: 10, nome: 'Fertilizante', insumos: 1 },
    { id: 11, nome: 'Nutrição animal', insumos: 1 },
    { id: 12, nome: 'Vazia', insumos: 0 },
  ])
})

describe('Filtros de insumos', () => {
  it('a busca não diferencia acento nem maiúscula, e diz quantos sobraram', async () => {
    const wrapper = await montarEm('/insumos')

    await wrapper.find('[data-teste="busca"]').setValue('UREIA')
    expect(nomes(wrapper)).toEqual(['Uréia agrícola'])
    expect(wrapper.find('[data-teste="contagem"]').text()).toContain('1 insumo de 3')

    await wrapper.findAll('[data-teste="contagem"] button').find((b) => b.text() === 'Limpar filtros')!.trigger('click')
    expect(nomes(wrapper)).toHaveLength(3)
    wrapper.unmount()
  })

  it('filtra pela categoria (ou sem categoria) e pela situação', async () => {
    const wrapper = await montarEm('/insumos')

    await wrapper.find('[data-teste="filtro-categoria"]').setValue('sem')
    expect(nomes(wrapper)).toEqual(['Calcário dolomítico'])
    await wrapper.find('[data-teste="filtro-categoria"]').setValue(11)
    expect(nomes(wrapper)).toEqual(['Sal mineral 80P'])

    await wrapper.find('[data-teste="filtro-categoria"]').setValue('')
    await wrapper.find('[data-teste="filtro-situacao"]').setValue('alta')
    expect(nomes(wrapper)).toEqual(['Uréia agrícola'])
    await wrapper.find('[data-teste="filtro-situacao"]').setValue('sem')
    expect(nomes(wrapper)).toEqual(['Calcário dolomítico'])
    wrapper.unmount()
  })

  it('mostra a categoria e o que está a caminho dos pedidos', async () => {
    const wrapper = await montarEm('/insumos')

    const linha = wrapper.findAll('tbody tr').find((tr) => tr.text().includes('Uréia'))!
    expect(linha.text()).toContain('Fertilizante')
    expect(linha.text()).toContain('+ 700 a caminho')
    wrapper.unmount()
  })

  it('o cadastro do insumo manda a categoria escolhida', async () => {
    vi.mocked(estoque.atualizarInsumo).mockResolvedValue({ ...calcario, categoria_id: 10 })
    const wrapper = await montarEm('/insumos')

    await wrapper.find('[aria-label="Alterar Calcário dolomítico"]').trigger('click')
    await wrapper.find('main form [data-teste="categoria"]').setValue(10)
    await wrapper.find('main form').trigger('submit')
    await flushPromises()

    expect(estoque.atualizarInsumo).toHaveBeenCalledWith(3, expect.objectContaining({ categoria_id: 10 }))
    wrapper.unmount()
  })
})

describe('Categorias', () => {
  it('o dono cria uma categoria; só a sem insumos tem "Remover"', async () => {
    vi.mocked(categorias.criarCategoria).mockResolvedValue({ id: 13, nome: 'Defensivo', insumos: 0 })
    const wrapper = await montarEm('/insumos')

    await wrapper.findAll('main button').find((b) => b.text() === 'Categorias')!.trigger('click')
    const linhas = [...document.querySelectorAll('[data-teste="categoria"]')]
    expect(linhas.map((l) => Boolean(l.querySelector('[aria-label^="Remover"]')))).toEqual([false, false, true])

    const campo = document.querySelector<HTMLInputElement>('[data-teste="nova-categoria"] input')!
    campo.value = 'Defensivo'
    campo.dispatchEvent(new Event('input'))
    document.querySelector('[data-teste="nova-categoria"]')!.dispatchEvent(new Event('submit'))
    await flushPromises()

    expect(categorias.criarCategoria).toHaveBeenCalledWith('Defensivo')
    expect(categorias.listarCategorias).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('o nome repetido mostra a frase da API na janela', async () => {
    vi.mocked(categorias.renomearCategoria).mockRejectedValue(
      new ApiError(409, { detail: 'Já existe uma categoria com esse nome.' }),
    )
    const wrapper = await montarEm('/insumos')

    await wrapper.findAll('main button').find((b) => b.text() === 'Categorias')!.trigger('click')
    document.querySelector<HTMLButtonElement>('[aria-label="Renomear Vazia"]')!.click()
    await flushPromises()
    const campo = document.querySelector<HTMLInputElement>('[aria-label="Novo nome da categoria"]')!
    campo.value = 'Fertilizante'
    campo.dispatchEvent(new Event('input'))
    campo.form!.dispatchEvent(new Event('submit'))
    await flushPromises()

    expect(categorias.renomearCategoria).toHaveBeenCalledWith(12, 'Fertilizante')
    expect(document.querySelector('[role="dialog"] [role="alert"]')?.textContent?.trim()).toBe(
      'Já existe uma categoria com esse nome.',
    )
    wrapper.unmount()
  })
})

describe('Filtros de movimentações', () => {
  it('com filtro, a API busca uma página e diz o total; "Carregar mais" traz a próxima', async () => {
    vi.mocked(estoque.buscarMovimentacoes)
      .mockResolvedValueOnce({ movimentacoes: [mov(1, 'entrada')], total: 2 })
      .mockResolvedValueOnce({ movimentacoes: [mov(3, 'entrada')], total: 2 })
    const wrapper = await montarEm('/movimentacoes')
    expect(estoque.buscarMovimentacoes).not.toHaveBeenCalled()

    await wrapper.find('[data-teste="filtro-tipo"]').setValue('entrada')
    await flushPromises()
    expect(estoque.buscarMovimentacoes).toHaveBeenCalledWith(
      { busca: '', tipo: 'entrada', desde: '', ate: '' },
      50,
      0,
    )
    expect(wrapper.find('[data-teste="contagem"]').text()).toContain('2 movimentações')

    await wrapper.findAll('main button').find((b) => b.text().startsWith('Carregar mais'))!.trigger('click')
    await flushPromises()
    expect(estoque.buscarMovimentacoes).toHaveBeenLastCalledWith(expect.objectContaining({ tipo: 'entrada' }), 50, 1)
    expect(wrapper.findAll('main tbody tr')).toHaveLength(2)
    expect(wrapper.findAll('main button').some((b) => b.text().startsWith('Carregar mais'))).toBe(false)
    wrapper.unmount()
  })

  it('limpar os filtros volta à lista das mais recentes', async () => {
    vi.mocked(estoque.buscarMovimentacoes).mockResolvedValue({ movimentacoes: [], total: 0 })
    const wrapper = await montarEm('/movimentacoes')

    await wrapper.find('[data-teste="filtro-desde"]').setValue('2026-01-01')
    await flushPromises()
    expect(wrapper.findAll('main tbody tr')).toHaveLength(0)

    await wrapper.findAll('[data-teste="contagem"] button').find((b) => b.text() === 'Limpar filtros')!.trigger('click')
    await flushPromises()
    expect(wrapper.findAll('main tbody tr')).toHaveLength(2)
    wrapper.unmount()
  })
})
