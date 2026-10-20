import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/App.vue'
import { routes } from '@/router'
import * as api from '@/services/estoque'
import type { Insumo, Movimentacao } from '@/types/api'

vi.mock('@/services/health', () => ({
  buscarHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
  buscarReadiness: vi.fn().mockResolvedValue({ status: 'pronto', database: 'ok' }),
}))
vi.mock('@/services/estoque', () => ({
  listarInsumos: vi.fn(),
  listarMovimentacoes: vi.fn(),
  registrarMovimentacao: vi.fn(),
}))

// Datas relativas a hoje, no mesmo formato da API (AAAA-MM-DD, fuso do navegador).
function diasAtras(dias: number) {
  const dia = new Date()
  dia.setDate(dia.getDate() - dias)
  return dia.toLocaleDateString('sv-SE')
}

const ureia: Insumo = {
  id: 1,
  nome: 'Ureia agrícola',
  unidade: 'kg',
  estoque_minimo: null,
  prazo_reposicao_dias: null,
  demonstracao: false,
  estoque_atual: 80,
  analise: { consumo_diario: null, cobertura_dias: null, alertas: [], reposicao: null, limitacoes: [] },
}
const mov = (id: number, dias: number, tipo: Movimentacao['tipo'], quantidade: number): Movimentacao => ({
  id,
  insumo_id: 1,
  tipo,
  data: diasAtras(dias),
  quantidade,
  validade: null,
})

async function montar() {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push('/movimentacoes')
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

describe('Movimentações no celular', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.listarInsumos).mockResolvedValue([ureia])
    // A API manda da mais recente para a mais antiga.
    vi.mocked(api.listarMovimentacoes).mockResolvedValue([
      mov(3, 0, 'saida', 12.5),
      mov(2, 1, 'saida', 10),
      mov(1, 5, 'entrada', 100),
    ])
  })

  it('agrupa por dia, como um extrato: hoje, ontem e o dia da semana', async () => {
    const wrapper = await montar()

    const dias = wrapper.findAll('[data-teste="dia"]').map((dia) => dia.text())
    expect(dias.slice(0, 2)).toEqual(['Hoje', 'Ontem'])
    expect(dias[2]).toMatch(/-feira|sábado|domingo/)
    expect(wrapper.findAll('[data-teste="movimentacao-celular"]').map((linha) => linha.text())).toEqual([
      expect.stringMatching(/Ureia agrícola.*Saída.*−12,5\s+kg/),
      expect.stringMatching(/Saída.*−10\s+kg/),
      expect.stringMatching(/Entrada.*\+100\s+kg/),
    ])
  })

  it('confirma em palavras o que acabou de ser lançado', async () => {
    vi.mocked(api.registrarMovimentacao).mockResolvedValue(mov(4, 0, 'saida', 3))
    const wrapper = await montar()

    await wrapper.find('select').setValue(1)
    await wrapper.find('input[type="number"]').setValue(3)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('[data-teste="confirmacao"]').text()).toBe(
      'Saída de 3 kg de Ureia agrícola lançada.',
    )
  })
})
