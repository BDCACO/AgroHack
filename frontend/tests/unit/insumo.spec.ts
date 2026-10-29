import { DOMWrapper, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/App.vue'
import GraficoDeEstoque from '@/components/GraficoDeEstoque.vue'
import { routes } from '@/router'
import * as api from '@/services/estoque'
import type { InsumoDetalhe } from '@/types/api'

vi.mock('@/services/health', () => ({
  buscarHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
  buscarReadiness: vi.fn().mockResolvedValue({ status: 'pronto', database: 'ok' }),
}))
vi.mock('@/services/estoque', () => ({
  buscarInsumo: vi.fn(),
  removerInsumo: vi.fn(),
  criarInsumo: vi.fn(),
  listarInsumos: vi.fn().mockResolvedValue([]),
  listarMovimentacoes: vi.fn().mockResolvedValue([]),
}))

// O ECharts não desenha no jsdom; o que importa é a configuração que recebe.
const setOption = vi.fn()
vi.mock('echarts/core', () => ({
  use: vi.fn(),
  init: () => ({ setOption, resize: vi.fn(), dispose: vi.fn() }),
  format: { encodeHTML: (texto: string) => texto.replaceAll('<', '&lt;') },
}))
vi.stubGlobal(
  'ResizeObserver',
  class {
    observe() {}
    disconnect() {}
  },
)

function ureia(): InsumoDetalhe {
  return {
    id: 7,
    nome: 'Ureia',
    unidade: 'kg',
    estoque_minimo: 10,
    prazo_reposicao_dias: 15,
    embalagem: null,
    pedido_minimo: null,
    carencia_dias: null,
    custo_medio: null,
    valor_em_estoque: null,
    demonstracao: false,
    estoque_atual: 21,
    analise: {
      consumo_diario: 2.5,
      cobertura_dias: 8.4,
      alertas: [{ tipo: 'risco_de_falta', gravidade: 'alta', justificativa: 'Dura 8 dias.' }],
      reposicao: {
        pedir_em: '2000-01-01',
        pedir_hoje: true,
        quantidade: 70,
        justificativa: 'Pedir hoje 70 kg.',
        custo_estimado: null,
      },
      limitacoes: [],
    },
    historico: [
      { data: '2026-10-01', saldo: 40 },
      { data: '2026-10-10', saldo: 21 },
    ],
    movimentacoes: [],
  }
}

async function montarEm(caminho: string) {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(caminho)
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}

describe('InsumoPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.buscarInsumo).mockResolvedValue(ureia())
  })

  it('resume o insumo e mostra os alertas sem repetir o nome', async () => {
    const { wrapper } = await montarEm('/insumos/7')

    expect(api.buscarInsumo).toHaveBeenCalledWith(7)
    expect(wrapper.find('main h1').text()).toBe('Ureia')
    expect(wrapper.findAll('main dd').map((dd) => dd.text())).toEqual([
      '21 kg',
      '2,5 kg/dia',
      '8 dias',
      'pedir hoje',
    ])
    expect(wrapper.find('[data-teste="alerta"] p').text()).toBe('Risco de falta')
    // O detalhe fica sob "Insumos" no menu.
    const ativo = wrapper.find('nav[aria-label="Principal"] a[aria-current="page"]')
    expect(ativo.text()).toBe('Insumos')
  })

  it('sem movimentação, ainda mostra os alertas (o Painel leva até aqui)', async () => {
    const novo = ureia()
    novo.historico = []
    vi.mocked(api.buscarInsumo).mockResolvedValue(novo)

    const { wrapper } = await montarEm('/insumos/7')

    expect(wrapper.text()).toContain('Nenhuma movimentação ainda')
    expect(wrapper.find('[data-teste="alerta"]').exists()).toBe(true)
  })

  it('remove depois de confirmar e volta para a lista', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { wrapper, router } = await montarEm('/insumos/7')

    const remover = wrapper.findAll('main button').find((b) => b.text() === 'Remover')!
    await remover.trigger('click')

    expect(api.removerInsumo).toHaveBeenCalledWith(7)
    // A lista entra por import() dinâmico: a navegação leva mais que um flush.
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('insumos'))
  })
})

describe('Reais no insumo', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('a página do insumo mostra custo médio, embalagem, valor em estoque e custo da reposição', async () => {
    const comPreco = ureia()
    Object.assign(comPreco, { custo_medio: 3.2, valor_em_estoque: 67.2, embalagem: 50 })
    comPreco.analise.reposicao = { ...comPreco.analise.reposicao!, quantidade: 100, custo_estimado: 320 }
    vi.mocked(api.buscarInsumo).mockResolvedValue(comPreco)

    const { wrapper } = await montarEm('/insumos/7')

    expect(wrapper.find('main header').text()).toMatch(
      /Embalagem de 50 kg\. Custo médio de R\$\s3,20\/kg\./,
    )
    const resumo = wrapper.findAll('main dd').map((dd) => dd.text())
    expect(resumo).toContainEqual(expect.stringMatching(/^R\$\s67,20 em estoque$/))
    expect(resumo).toContainEqual(expect.stringMatching(/^100 kg, cerca de R\$\s320,00$/))
  })

  it('o cadastro manda a embalagem e o pedido mínimo, na unidade do insumo', async () => {
    vi.mocked(api.criarInsumo).mockImplementation(async (dados) => ({ ...ureia(), ...dados }))
    const { wrapper } = await montarEm('/insumos')

    await wrapper.findAll('main button').find((b) => b.text() === 'Cadastrar insumo')!.trigger('click')
    const form = new DOMWrapper(document.querySelector('[role="dialog"] [data-teste="form-insumo"]')!)
    const campos = form.findAll('label')
    const campo = (rotulo: string) => campos.find((l) => l.text().startsWith(rotulo))!.find('input')
    await campo('Nome').setValue('Ureia')
    await campo('Unidade').setValue('kg')
    expect(campos.find((l) => l.text().startsWith('Embalagem'))!.text()).toContain('Embalagem, em kg')
    await campo('Embalagem').setValue(50)
    await campo('Pedido mínimo').setValue(100)
    await form.trigger('submit')
    await flushPromises()

    expect(api.criarInsumo).toHaveBeenCalledWith(
      expect.objectContaining({ nome: 'Ureia', unidade: 'kg', embalagem: 50, pedido_minimo: 100 }),
    )
  })
})

describe('GraficoDeEstoque', () => {
  it('projeta até o estoque zerar, e escapa o texto do usuário no tooltip', () => {
    const insumo = { ...ureia(), unidade: '<b>kg' }

    const grafico = mount(GraficoDeEstoque, { props: { insumo, hoje: '2026-10-19' } })

    const opcoes = setOption.mock.lastCall![0]
    // Saldo mantido até hoje; a projeção usa a cobertura da API (8,4 dias), arredondada como
    // no cartão "Dura cerca de 8 dias".
    expect(opcoes.series[0].data.at(-1)).toEqual(['2026-10-19', 21])
    expect(opcoes.series[1].data).toEqual([
      ['2026-10-19', 21],
      ['2026-10-27', 0],
    ])
    expect(grafico.attributes('aria-label')).toContain('no ritmo atual, zera em ~8 dias.')
    const tooltip = opcoes.tooltip.formatter([{ seriesName: 'Estoque', value: ['2026-10-19', 21] }])
    expect(tooltip).toBe('19/10/2026<br>Estoque: 21 &lt;b>kg')
  })
})
