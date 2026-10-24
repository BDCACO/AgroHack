import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import PainelPage from '@/pages/PainelPage.vue'
import { routes } from '@/router'
import * as api from '@/services/estoque'
import { ApiError } from '@/services/http'
import { useEstoqueStore } from '@/stores/estoque'
import type { Alerta, Insumo, Resumo } from '@/types/api'

vi.mock('@/services/estoque', async (original) => ({
  ...(await original<typeof import('@/services/estoque')>()),
  listarInsumos: vi.fn(),
  listarMovimentacoes: vi.fn(),
  registrarMovimentacao: vi.fn(),
  buscarResumo: vi.fn(),
  baixarRelatorio: vi.fn(),
}))

function insumo(id: number, nome: string, alertas: Alerta[] = []): Insumo {
  return {
    id,
    nome,
    demonstracao: false,
    unidade: 'kg',
    estoque_minimo: null,
    prazo_reposicao_dias: null,
    embalagem: null,
    pedido_minimo: null,
    carencia_dias: null,
    custo_medio: null,
    valor_em_estoque: null,
    estoque_atual: 10,
    analise: {
      consumo_diario: 1,
      cobertura_dias: 10,
      alertas,
      reposicao: null,
      limitacoes: ['Consumo é a média dos últimos 90 dias.'],
    },
  }
}

function resumo(mudancas: Partial<Resumo> = {}): Resumo {
  return {
    insumos: 2,
    valor_em_estoque: 1234.5,
    insumos_sem_preco: 0,
    perdas: { ultimos_30_dias: 80, total: 210.25 },
    compras_sugeridas: { valor: 3500, pedidos: 2, pedir_hoje: 1 },
    alertas: { alta: 1, media: 0, baixa: 1 },
    talhoes_em_carencia: 0,
    limitacoes: [],
    ...mudancas,
  }
}

const excesso: Alerta = { tipo: 'excesso', gravidade: 'baixa', justificativa: 'Dura 400 dias.' }
const falta: Alerta = { tipo: 'risco_de_falta', gravidade: 'alta', justificativa: 'Dura 3 dias.' }

describe('useEstoqueStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    vi.mocked(api.listarMovimentacoes).mockResolvedValue([])
  })

  it('junta os alertas de todos os insumos, os mais graves primeiro', async () => {
    vi.mocked(api.listarInsumos).mockResolvedValue([
      insumo(1, 'Calcário', [excesso]),
      insumo(2, 'Ureia', [falta]),
    ])
    const store = useEstoqueStore()

    await store.carregar()

    expect(store.alertas.map((a) => [a.insumo.nome, a.alerta.tipo])).toEqual([
      ['Ureia', 'risco_de_falta'],
      ['Calcário', 'excesso'],
    ])
  })

  it('recarrega os insumos depois de lançar uma movimentação', async () => {
    vi.mocked(api.listarInsumos).mockResolvedValue([])
    const store = useEstoqueStore()

    await store.registrarMovimentacao({
      insumo_id: 1,
      tipo: 'saida',
      data: '2026-10-19',
      quantidade: 2,
      validade: null,
    })

    expect(api.registrarMovimentacao).toHaveBeenCalledOnce()
    expect(api.listarInsumos).toHaveBeenCalledOnce()
  })

  it('guarda uma mensagem legível quando a API não responde', async () => {
    vi.mocked(api.listarInsumos).mockRejectedValue(new ApiError(null))
    const store = useEstoqueStore()

    await store.carregar()

    expect(store.erro).toBe('Sem resposta do servidor. Tente de novo em instantes.')
    expect(store.carregado).toBe(false)
  })
})

describe('PainelPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    vi.mocked(api.listarMovimentacoes).mockResolvedValue([])
  })

  async function montar() {
    const router = createRouter({ history: createMemoryHistory(), routes })
    const wrapper = mount(PainelPage, { global: { plugins: [router] } })
    await flushPromises()
    return wrapper
  }

  it('mostra cada alerta com a justificativa e a reposição sugerida', async () => {
    const ureia = insumo(2, 'Ureia', [falta])
    ureia.analise.reposicao = {
      pedir_em: '2000-01-01',
      pedir_hoje: true,
      quantidade: 70,
      justificativa: 'Pedir hoje 70 kg: cobre 30 dias de consumo.',
      custo_estimado: null,
    }
    vi.mocked(api.listarInsumos).mockResolvedValue([insumo(1, 'Calcário', [excesso]), ureia])

    const wrapper = await montar()

    const alertas = wrapper.findAll('[data-teste="alerta"]')
    expect(alertas.map((a) => a.findAll('p').map((p) => p.text()))).toEqual([
      ['Risco de falta · Ureia', 'Dura 3 dias.'],
      ['Excesso de estoque · Calcário', 'Dura 400 dias.'],
    ])
    const reposicao = wrapper.find('[data-teste="reposicao"]').text()
    expect(reposicao).toContain('pedir hoje')
    expect(reposicao).toContain('Pedir hoje 70 kg')
    const whatsapp = wrapper.find('[data-teste="whatsapp"]').attributes('href')!
    expect(decodeURIComponent(whatsapp)).toContain('\nPedir agora:\n- Ureia: 70 kg')
    expect(decodeURIComponent(whatsapp)).not.toContain('Próximos pedidos')
    await wrapper.find('[data-teste="relatorio"]').trigger('click')
    expect(api.baixarRelatorio).toHaveBeenCalledOnce()
  })

  it('os cartões de gravidade filtram a lista, e um segundo clique desfaz', async () => {
    vi.mocked(api.listarInsumos).mockResolvedValue([
      insumo(1, 'Calcário', [excesso]),
      insumo(2, 'Ureia', [falta]),
    ])
    const wrapper = await montar()
    const urgentes = wrapper.findAll('[role="group"] button')[0]!

    await urgentes.trigger('click')
    expect(urgentes.attributes('aria-pressed')).toBe('true')
    expect(wrapper.findAll('[data-teste="alerta"]').map((a) => a.text())).toEqual([
      expect.stringContaining('Ureia'),
    ])

    await urgentes.trigger('click')
    expect(wrapper.findAll('[data-teste="alerta"]')).toHaveLength(2)
  })

  it('barras de cobertura: falta, pedir hoje e folga, do mais apertado ao mais folgado', async () => {
    const ureia = insumo(1, 'Ureia', [falta])
    ureia.analise.cobertura_dias = 3
    const sal = insumo(2, 'Sal', [])
    sal.analise.cobertura_dias = 20
    sal.analise.reposicao = { pedir_em: '2000-01-01', pedir_hoje: true, quantidade: 5, justificativa: '', custo_estimado: null }
    const calcario = insumo(3, 'Calcário', [excesso])
    calcario.analise.cobertura_dias = 400
    vi.mocked(api.listarInsumos).mockResolvedValue([calcario, sal, ureia])

    const wrapper = await montar()

    const linhas = wrapper.findAll('[data-teste="cobertura"]').map((l) => l.text())
    expect(linhas).toEqual([
      expect.stringMatching(/Ureia.*3 dias.*acaba antes da entrega/),
      expect.stringMatching(/Sal.*20 dias.*pedir hoje/),
      expect.stringMatching(/Calcário.*400 dias.*estoque de sobra/),
    ])
  })

  it('sem insumos, convida a cadastrar', async () => {
    vi.mocked(api.listarInsumos).mockResolvedValue([])

    const wrapper = await montar()

    expect(wrapper.text()).toContain('Nenhum insumo cadastrado ainda')
    expect(wrapper.find('[data-teste="alerta"]').exists()).toBe(false)
  })

  it('mostra o estoque em reais: valor, compras dos próximos 30 dias e perdas', async () => {
    vi.mocked(api.listarInsumos).mockResolvedValue([insumo(1, 'Ureia')])
    vi.mocked(api.buscarResumo).mockResolvedValue(resumo())

    const wrapper = await montar()

    const cartoes = wrapper.findAll('[data-teste="em-reais"] dl > div').map((c) => c.text())
    expect(cartoes).toEqual([
      expect.stringMatching(/Valor em estoque\s*R\$\s1\.234,50\s*pelo custo médio/),
      expect.stringMatching(/Compras, próximos 30 dias\s*R\$\s3\.500,00\s*2 pedidos, 1 para hoje/),
      expect.stringMatching(/Perdas, últimos 30 dias\s*R\$\s80,00\s*descartes e faltas · R\$\s210,25 no total/),
    ])
  })

  it('sem preço nas compras, diz o que falta em vez de mostrar R$ 0,00', async () => {
    vi.mocked(api.listarInsumos).mockResolvedValue([insumo(1, 'Ureia')])
    vi.mocked(api.buscarResumo).mockResolvedValue(
      resumo({
        valor_em_estoque: null,
        insumos_sem_preco: 1,
        perdas: { ultimos_30_dias: 0, total: 0 },
        compras_sugeridas: { valor: null, pedidos: 0, pedir_hoje: 0 },
        limitacoes: ['1 insumo sem preço nas compras fica fora do valor em estoque.'],
      }),
    )

    const wrapper = await montar()

    const emReais = wrapper.find('[data-teste="em-reais"]').text()
    expect(emReais).toContain('lance o preço nas compras')
    expect(emReais).toContain('nada a pedir')
    expect(emReais).toContain('1 insumo sem preço nas compras fica fora do valor em estoque.')
    expect(emReais).not.toMatch(/Valor em estoque\s*R\$/)
  })

  it('a reposição diz quanto custa, quando há preço', async () => {
    const ureia = insumo(2, 'Ureia', [falta])
    ureia.analise.reposicao = {
      pedir_em: '2000-01-01',
      pedir_hoje: true,
      quantidade: 100,
      justificativa: 'Pedir hoje 2 sacos de 50 kg.',
      custo_estimado: 320,
    }
    vi.mocked(api.listarInsumos).mockResolvedValue([ureia])

    const wrapper = await montar()

    expect(wrapper.find('[data-teste="reposicao"]').text()).toMatch(/cerca de R\$\s320,00/)
  })

  it('sem o resumo (a API falhou nele), o Painel mostra o resto', async () => {
    vi.mocked(api.listarInsumos).mockResolvedValue([insumo(1, 'Ureia', [falta])])
    vi.mocked(api.buscarResumo).mockRejectedValue(new ApiError(500))

    const wrapper = await montar()

    expect(wrapper.find('[data-teste="em-reais"]').exists()).toBe(false)
    expect(wrapper.findAll('[data-teste="alerta"]')).toHaveLength(1)
  })
})
