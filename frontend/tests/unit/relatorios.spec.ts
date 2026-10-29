import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/App.vue'
import { routes } from '@/router'
import { ApiError } from '@/services/http'
import { baixarRelatorioPorPeriodo, buscarRelatorioPorPeriodo } from '@/services/relatorios'
import type { PeriodoDoRelatorio, RelatorioPorPeriodo } from '@/types/api'

vi.mock('@/services/health', () => ({
  buscarHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
  buscarReadiness: vi.fn().mockResolvedValue({ status: 'pronto', database: 'ok' }),
}))
vi.mock('@/services/estoque', async (original) => ({
  ...(await original<typeof import('@/services/estoque')>()),
  listarInsumos: vi.fn().mockResolvedValue([]),
  listarMovimentacoes: vi.fn().mockResolvedValue([]),
}))
vi.mock('@/services/compras', () => ({ listarFornecedores: vi.fn().mockResolvedValue([]) }))
vi.mock('@/services/relatorios', () => ({ buscarRelatorioPorPeriodo: vi.fn(), baixarRelatorioPorPeriodo: vi.fn() }))

// O ECharts não desenha no jsdom; o que importa é a configuração que recebe.
const setOption = vi.fn()
vi.mock('echarts/core', () => ({
  use: vi.fn(),
  init: () => ({ setOption, resize: vi.fn(), dispose: vi.fn() }),
}))
vi.stubGlobal(
  'ResizeObserver',
  class {
    observe() {}
    disconnect() {}
  },
)

const vazio = { consumo: [], gasto: 0, compras_sem_preco: 0, perdas: 0, perdas_sem_preco: 0, por_categoria: [], por_fornecedor: [] }
const setembro: PeriodoDoRelatorio = { ...vazio, inicio: '2026-09-01', fim: '2026-09-30', rotulo: 'set/2026' }
const outubro: PeriodoDoRelatorio = {
  inicio: '2026-10-01',
  fim: '2026-10-27',
  rotulo: 'out/2026',
  consumo: [
    { insumo_id: 1, insumo: 'Ureia agrícola', unidade: 'kg', quantidade: 300, valor: 948 },
    { insumo_id: 2, insumo: 'Calcário', unidade: 't', quantidade: 2, valor: null },
  ],
  gasto: 2212,
  compras_sem_preco: 1,
  perdas: 326.7,
  perdas_sem_preco: 0,
  por_categoria: [{ categoria_id: 1, categoria: 'Fertilizante', gasto: 2212, consumo: 948, perdas: 0 }],
  por_fornecedor: [{ fornecedor_id: 7, fornecedor: 'Agro Ariquemes', gasto: 2212, compras: 2, compras_sem_preco: 1 }],
}
const relatorio: RelatorioPorPeriodo = {
  desde: '2026-09-01',
  ate: '2026-10-27',
  agrupar: 'mes',
  periodos: [setembro, outubro],
  total: { ...outubro },
  limitacoes: ['Consumo e perdas em reais pelo custo médio de hoje, não pelo preço da época.'],
}

async function montar() {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push('/relatorios')
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  vi.mocked(buscarRelatorioPorPeriodo).mockResolvedValue(relatorio)
})

describe('Relatórios', () => {
  it('sem filtro, pede os últimos 12 meses por mês e mostra os totais em reais', async () => {
    const wrapper = await montar()

    expect(buscarRelatorioPorPeriodo).toHaveBeenCalledWith(expect.objectContaining({ desde: '', ate: '', agrupar: 'mes' }))
    expect(wrapper.find('[data-teste="intervalo"]').text()).toBe('De 01/09/2026 a 27/10/2026')
    expect(wrapper.find('[data-teste="total-gasto"]').text()).toMatch(/R\$\s2\.212,00/)
    expect(wrapper.find('[data-teste="total-gasto"]').text()).toContain('Fora da conta: 1 compra sem preço')
    // O consumo em reais soma o que a API valorou; o calcário sem preço fica fora.
    expect(wrapper.find('[data-teste="total-consumo"]').text()).toMatch(/R\$\s948,00/)
    expect(wrapper.find('[data-teste="total-perdas"]').text()).toMatch(/R\$\s326,70/)
    expect(wrapper.find('[data-teste="limitacoes"]').text()).toContain('custo médio de hoje')
  })

  it('o gráfico recebe um grupo de barras por período: gasto, consumo e perdas', async () => {
    await montar()

    const opcoes = setOption.mock.lastCall![0]
    expect(opcoes.xAxis.data).toEqual(['set/2026', 'out/2026'])
    expect(opcoes.series.map((s: { name: string }) => s.name)).toEqual(['Gasto em compras', 'Consumo', 'Perdas'])
    expect(opcoes.series.map((s: { data: number[] }) => s.data)).toEqual([
      [0, 2212],
      [0, 948],
      [0, 326.7],
    ])
  })

  it('lista o consumo por insumo, o mais caro primeiro, e os totais por categoria e fornecedor', async () => {
    const wrapper = await montar()

    const consumo = wrapper.findAll('[data-teste="consumo-insumo"]').map((linha) => linha.text())
    expect(consumo[0]).toMatch(/Ureia agrícola\s*300 kg\s*R\$\s948,00/)
    expect(consumo[1]).toMatch(/Calcário\s*2 t\s*—/)
    expect(wrapper.find('[data-teste="categoria"]').text()).toMatch(/Fertilizante\s*R\$\s2\.212,00\s*R\$\s948,00\s*R\$\s0,00/)
    expect(wrapper.find('[data-teste="por-fornecedor"]').text()).toMatch(/Agro Ariquemes\s*2 compras\s*, 1 sem preço\s*R\$\s2\.212,00/)
  })

  it('trocar o agrupamento ou o período pede de novo', async () => {
    const wrapper = await montar()

    await wrapper.find('[data-teste="agrupar"]').setValue('semana')
    await flushPromises()
    expect(buscarRelatorioPorPeriodo).toHaveBeenLastCalledWith(expect.objectContaining({ agrupar: 'semana' }))

    await wrapper.find('[data-teste="desde"]').setValue('2026-10-01')
    await flushPromises()
    expect(buscarRelatorioPorPeriodo).toHaveBeenLastCalledWith(
      expect.objectContaining({ agrupar: 'semana', desde: '2026-10-01' }),
    )
  })

  it('baixa em PDF e em Excel, com os filtros da tela', async () => {
    vi.mocked(baixarRelatorioPorPeriodo).mockResolvedValue()
    const wrapper = await montar()
    await wrapper.find('[data-teste="agrupar"]').setValue('semana')
    await wrapper.find('[data-teste="desde"]').setValue('2026-10-01')
    await flushPromises()

    await wrapper.find('[data-teste="baixar-pdf"]').trigger('click')
    await flushPromises()
    expect(baixarRelatorioPorPeriodo).toHaveBeenLastCalledWith(
      expect.objectContaining({ agrupar: 'semana', desde: '2026-10-01' }),
      'pdf',
    )
    await wrapper.find('[data-teste="baixar-excel"]').trigger('click')
    await flushPromises()
    expect(baixarRelatorioPorPeriodo).toHaveBeenLastCalledWith(expect.objectContaining({ agrupar: 'semana' }), 'xlsx')
  })

  it('o arquivo recusado mostra a frase da API ao lado do botão', async () => {
    vi.mocked(baixarRelatorioPorPeriodo).mockRejectedValue(
      new ApiError(422, { detail: 'O período começa depois de terminar: troque as datas.' }),
    )
    const wrapper = await montar()

    await wrapper.find('[data-teste="baixar-pdf"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('header [role="alert"], main [role="alert"]').text()).toBe(
      'O período começa depois de terminar: troque as datas.',
    )
  })

  it('a recusa da API (período grande demais por dia) aparece com a frase dela', async () => {
    const wrapper = await montar()
    vi.mocked(buscarRelatorioPorPeriodo).mockRejectedValue(
      new ApiError(422, { detail: 'São mais de 400 períodos: agrupe por semana ou por mês.' }),
    )

    await wrapper.find('[data-teste="agrupar"]').setValue('dia')
    await flushPromises()

    expect(wrapper.find('[data-teste="erro"]').text()).toBe('São mais de 400 períodos: agrupe por semana ou por mês.')
  })
})
