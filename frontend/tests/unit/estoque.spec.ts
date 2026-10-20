import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import PainelPage from '@/pages/PainelPage.vue'
import { routes } from '@/router'
import * as api from '@/services/estoque'
import { ApiError } from '@/services/http'
import { useEstoqueStore } from '@/stores/estoque'
import type { Alerta, Insumo } from '@/types/api'

vi.mock('@/services/estoque', async (original) => ({
  ...(await original<typeof import('@/services/estoque')>()),
  listarInsumos: vi.fn(),
  listarMovimentacoes: vi.fn(),
  registrarMovimentacao: vi.fn(),
}))

function insumo(id: number, nome: string, alertas: Alerta[] = []): Insumo {
  return {
    id,
    nome,
    demonstracao: false,
    unidade: 'kg',
    estoque_minimo: null,
    prazo_reposicao_dias: null,
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
    expect(wrapper.find('[data-teste="relatorio"]').attributes('href')).toBe(
      '/api/v1/relatorio.xlsx',
    )
  })

  it('sem insumos, convida a cadastrar', async () => {
    vi.mocked(api.listarInsumos).mockResolvedValue([])

    const wrapper = await montar()

    expect(wrapper.text()).toContain('Nenhum insumo cadastrado ainda')
    expect(wrapper.find('[data-teste="alerta"]').exists()).toBe(false)
  })
})
