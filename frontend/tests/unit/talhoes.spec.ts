import { DOMWrapper, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/App.vue'
import { routes } from '@/router'
import * as estoque from '@/services/estoque'
import { ApiError } from '@/services/http'
import * as api from '@/services/talhoes'
import { useSessaoStore } from '@/stores/sessao'
import type { Insumo, Talhao, TalhaoDetalhe } from '@/types/api'

// Movimentações carrega os fornecedores para a compra.
vi.mock('@/services/compras', () => ({ listarFornecedores: vi.fn().mockResolvedValue([]) }))
vi.mock('@/services/health', () => ({
  buscarHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
  buscarReadiness: vi.fn().mockResolvedValue({ status: 'pronto', database: 'ok' }),
}))
vi.mock('@/services/estoque', () => ({
  listarInsumos: vi.fn(),
  listarMovimentacoes: vi.fn(),
  registrarMovimentacao: vi.fn(),
  criarInsumo: vi.fn(),
  buscarResumo: vi.fn().mockRejectedValue(new Error('sem resumo aqui')),
  baixarRelatorio: vi.fn(),
}))
vi.mock('@/services/talhoes', () => ({
  listarTalhoes: vi.fn(),
  buscarTalhao: vi.fn(),
  criarTalhao: vi.fn(),
  atualizarTalhao: vi.fn(),
  removerTalhao: vi.fn(),
}))

const glifosato: Insumo = {
  id: 5,
  nome: 'Glifosato 480',
  unidade: 'L',
  estoque_minimo: null,
  prazo_reposicao_dias: null,
  embalagem: null,
  pedido_minimo: null,
  carencia_dias: 7,
  custo_medio: 29,
  valor_em_estoque: 290,
  demonstracao: false,
  estoque_atual: 10,
  analise: { consumo_diario: null, cobertura_dias: null, alertas: [], reposicao: null, limitacoes: [] },
}

const CARENCIA =
  'Talhão Norte: não colher nem abater antes de 29/10/2026 (faltam 5 dias). Glifosato 480 aplicado em 22/10/2026, carência de 7 dias.'

function talhao(id: number, nome: string, mudancas: Partial<Talhao> = {}): Talhao {
  return {
    id,
    nome,
    area_ha: 120,
    cultura: 'Soja',
    demonstracao: false,
    colheita_liberada_em: null,
    em_carencia: false,
    alertas: [],
    custo_total: null,
    custo_por_ha: null,
    limitacoes: [],
    ...mudancas,
  }
}
const norte = talhao(1, 'Talhão Norte', {
  colheita_liberada_em: '2026-10-29',
  em_carencia: true,
  alertas: [{ tipo: 'carencia', gravidade: 'alta', justificativa: CARENCIA }],
  custo_total: 8126.55,
  custo_por_ha: 67.72,
})
const sul = talhao(2, 'Talhão Sul', { cultura: 'Milho', area_ha: 80, colheita_liberada_em: '2026-09-01' })

async function montarEm(caminho: string) {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(caminho)
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return { wrapper, router }
}

const botoes = (wrapper: ReturnType<typeof mount>) => wrapper.findAll('main button').map((b) => b.text())

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  document.body.innerHTML = ''
  vi.mocked(estoque.listarInsumos).mockResolvedValue([glifosato])
  vi.mocked(estoque.listarMovimentacoes).mockResolvedValue([])
  vi.mocked(api.listarTalhoes).mockResolvedValue([norte, sul])
})

describe('Talhões', () => {
  it('lista cada talhão com a carência (quando há) e o custo por hectare', async () => {
    const { wrapper } = await montarEm('/talhoes')

    const cartoes = wrapper.findAll('[data-teste="talhao"]')
    expect(cartoes).toHaveLength(2)
    expect(cartoes[0]!.find('[data-teste="carencia"]').text()).toBe(CARENCIA)
    expect(cartoes[0]!.text()).toMatch(/Soja · 120 ha/)
    expect(cartoes[0]!.text()).toMatch(/Por hectare\s*R\$\s67,72/)
    expect(cartoes[1]!.text()).toContain('Colheita liberada desde 01/09/2026.')
    expect(cartoes[1]!.text()).toMatch(/Custo aplicado\s*—/)
  })

  it('o dono cadastra um talhão com a área e a cultura', async () => {
    vi.mocked(api.criarTalhao).mockResolvedValue(talhao(3, 'Pasto 1'))
    const { wrapper } = await montarEm('/talhoes')

    await wrapper.findAll('main button').find((b) => b.text() === 'Novo talhão')!.trigger('click')
    const campos = wrapper.findAll('main form input')
    await campos[0]!.setValue('Pasto 1')
    await campos[1]!.setValue(45)
    await campos[2]!.setValue('Pasto')
    await wrapper.find('main form').trigger('submit')
    await flushPromises()

    expect(api.criarTalhao).toHaveBeenCalledWith({ nome: 'Pasto 1', area_ha: 45, cultura: 'Pasto' })
    expect(api.listarTalhoes).toHaveBeenCalledTimes(2)
    expect(wrapper.find('main form').exists()).toBe(false)
  })

  it('talhão com aplicações não se remove: a frase da API aparece na janela', async () => {
    vi.mocked(api.removerTalhao).mockRejectedValue(
      new ApiError(409, { detail: 'O talhão tem 3 aplicações: não dá para removê-lo.' }),
    )
    const { wrapper } = await montarEm('/talhoes')

    await wrapper.find('[aria-label="Remover Talhão Norte"]').trigger('click')
    await flushPromises()
    const confirmar = document.querySelector<HTMLButtonElement>('[data-teste="confirmar-remocao"]')!
    confirmar.click()
    await flushPromises()

    expect(api.removerTalhao).toHaveBeenCalledWith(1)
    expect(document.querySelector('[role="dialog"] [role="alert"]')?.textContent?.trim()).toBe(
      'O talhão tem 3 aplicações: não dá para removê-lo.',
    )
    expect(wrapper.findAll('[data-teste="talhao"]')).toHaveLength(2)
    wrapper.unmount()
  })

  it('o funcionário consulta, mas não cadastra, altera nem remove', async () => {
    useSessaoStore().usuario = { id: 2, nome: 'Zé', login: 'ze', papel: 'funcionario' }
    const { wrapper } = await montarEm('/talhoes')

    expect(wrapper.findAll('[data-teste="talhao"]')).toHaveLength(2)
    expect(botoes(wrapper)).not.toContain('Novo talhão')
    expect(botoes(wrapper)).not.toContain('Alterar')
    expect(botoes(wrapper)).not.toContain('Remover')
  })
})

describe('Página do talhão', () => {
  const detalhe: TalhaoDetalhe = {
    ...norte,
    consumo: [{ insumo_id: 5, insumo: 'Glifosato 480', unidade: 'L', quantidade: 280, custo: 8120 }],
    aplicacoes: [
      { id: 40, insumo_id: 5, tipo: 'saida', data: '2026-10-22', quantidade: 280, validade: null, talhao_id: 1, lancado_por: 'Zé' },
    ],
  }

  it('mostra a carência, o que foi aplicado e cada aplicação; o período refaz a conta', async () => {
    vi.mocked(api.buscarTalhao).mockResolvedValue(detalhe)
    const { wrapper } = await montarEm('/talhoes/1')

    expect(api.buscarTalhao).toHaveBeenCalledWith(1, { desde: '', ate: '' })
    expect(wrapper.find('main h1').text()).toBe('Talhão Norte')
    expect(wrapper.find('[data-teste="alerta"]').text()).toContain('Em carência')
    expect(wrapper.find('[data-teste="consumo"]').text()).toMatch(/Glifosato 480\s*280 L\s*R\$\s8\.120,00/)
    expect(wrapper.find('[data-teste="aplicacao"]').text()).toMatch(/22\/10\/2026\s*Glifosato 480\s*· por Zé\s*280\s*L/)
    // A aba Talhões fica acesa no detalhe.
    expect(wrapper.find('nav[aria-label="Principal"] a[aria-current="page"]').text()).toBe('Talhões')

    await wrapper.find('[data-teste="desde"]').setValue('2026-09-01')
    await flushPromises()
    expect(api.buscarTalhao).toHaveBeenLastCalledWith(1, { desde: '2026-09-01', ate: '' })
  })
})

describe('Talhões nas outras telas', () => {
  it('uma retirada diz em que talhão foi aplicada, e a confirmação repete', async () => {
    vi.mocked(estoque.registrarMovimentacao).mockResolvedValue({
      id: 41,
      insumo_id: 5,
      tipo: 'saida',
      data: '2026-10-24',
      quantidade: 20,
      validade: null,
      talhao_id: 1,
    })
    const { wrapper } = await montarEm('/movimentacoes')

    await wrapper.find('main select').setValue(5)
    await wrapper.find('input[type="number"]').setValue(20)
    await wrapper.find('[data-teste="talhao"]').setValue(1)
    await wrapper.find('main form').trigger('submit')
    await flushPromises()

    expect(estoque.registrarMovimentacao).toHaveBeenCalledWith(
      expect.objectContaining({ tipo: 'saida', talhao_id: 1 }),
    )
    expect(wrapper.find('[data-teste="confirmacao"]').text()).toBe(
      'Saída de 20 L de Glifosato 480 no Talhão Norte lançada.',
    )

    // Numa entrada (compra), não há talhão.
    await wrapper.find('input[value="entrada"]').setValue(true)
    expect(wrapper.find('[data-teste="talhao"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('o Painel mostra à parte os talhões em que não se pode colher', async () => {
    const { wrapper } = await montarEm('/')

    const bloco = wrapper.find('[data-teste="talhoes-em-carencia"]')
    expect(bloco.text()).toContain('Não colher')
    expect(bloco.text()).toContain('Talhão Norte em carência')
    expect(bloco.text()).toContain(CARENCIA)
    expect(bloco.text()).not.toContain('Talhão Sul')
  })

  it('o cadastro do insumo manda a carência', async () => {
    vi.mocked(estoque.criarInsumo).mockImplementation(async (dados) => ({ ...glifosato, ...dados }))
    vi.mocked(estoque.listarInsumos).mockResolvedValue([])
    const { wrapper } = await montarEm('/insumos')

    await wrapper.findAll('main button').find((b) => b.text() === 'Cadastrar insumo')!.trigger('click')
    const form = new DOMWrapper(document.querySelector('[role="dialog"] [data-teste="form-insumo"]')!)
    const campo = (rotulo: string) => form.findAll('label').find((l) => l.text().startsWith(rotulo))!.find('input')
    await campo('Nome').setValue('Fungicida X')
    await campo('Unidade').setValue('L')
    await campo('Carência').setValue(15)
    await form.trigger('submit')
    await flushPromises()

    expect(estoque.criarInsumo).toHaveBeenCalledWith(expect.objectContaining({ carencia_dias: 15 }))
  })
})
