import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/App.vue'
import { routes } from '@/router'
import * as api from '@/services/estoque'
import { ApiError } from '@/services/http'
import type { Insumo, Movimentacao } from '@/types/api'

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
  removerMovimentacao: vi.fn(),
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
  embalagem: null,
  pedido_minimo: null,
  carencia_dias: null,
  custo_medio: null,
  valor_em_estoque: null,
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
  // Preso ao documento: a janela de confirmação vai para o <body> (Teleport).
  const wrapper = mount(App, { global: { plugins: [router] }, attachTo: document.body })
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

describe('Preço da compra', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.listarInsumos).mockResolvedValue([ureia])
    vi.mocked(api.listarMovimentacoes).mockResolvedValue([])
    vi.mocked(api.registrarMovimentacao).mockReset()
  })

  it('numa entrada, manda o preço por unidade e o repete na confirmação', async () => {
    vi.mocked(api.registrarMovimentacao).mockResolvedValue({
      ...mov(4, 0, 'entrada', 100),
      valor_unitario: 3.2,
    })
    const wrapper = await montar()

    await wrapper.find('input[value="entrada"]').setValue(true)
    await wrapper.find('select').setValue(1)
    expect(wrapper.find('[data-teste="preco"]').element.closest('label')?.textContent).toContain(
      'Preço (R$/kg)',
    )
    await wrapper.find('input[type="number"]').setValue(100)
    await wrapper.find('[data-teste="preco"]').setValue(3.2)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(api.registrarMovimentacao).toHaveBeenCalledWith(
      expect.objectContaining({ tipo: 'entrada', quantidade: 100, valor_unitario: 3.2 }),
    )
    expect(wrapper.find('[data-teste="confirmacao"]').text()).toMatch(
      /^Entrada de 100 kg de Ureia agrícola, a R\$\s3,20\/kg lançada\.$/,
    )
    wrapper.unmount()
  })

  it('numa saída, não há campo de preço, e o que foi digitado não vai junto', async () => {
    vi.mocked(api.registrarMovimentacao).mockResolvedValue(mov(4, 0, 'saida', 3))
    const wrapper = await montar()

    await wrapper.find('input[value="entrada"]').setValue(true)
    await wrapper.find('[data-teste="preco"]').setValue(3.2)
    await wrapper.find('input[value="saida"]').setValue(true)
    expect(wrapper.find('[data-teste="preco"]').exists()).toBe(false)

    await wrapper.find('select').setValue(1)
    await wrapper.find('input[type="number"]').setValue(3)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(api.registrarMovimentacao).toHaveBeenCalledWith(
      expect.objectContaining({ tipo: 'saida', valor_unitario: null }),
    )
    wrapper.unmount()
  })
})

describe('Remover movimentação', () => {
  const janela = () => document.querySelector<HTMLElement>('[role="dialog"]')
  const botao = (texto: string) =>
    [...(janela()?.querySelectorAll('button') ?? [])].find((b) => b.textContent?.trim() === texto)!

  async function abrirJanela() {
    const wrapper = await montar()
    const linha = wrapper.findAll('button').find((b) => b.text() === 'Remover')!
    await linha.trigger('click')
    await flushPromises()
    return wrapper
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.listarInsumos).mockResolvedValue([ureia])
    vi.mocked(api.listarMovimentacoes).mockResolvedValue([mov(3, 0, 'saida', 12.5)])
    vi.mocked(api.removerMovimentacao).mockReset()
    document.body.innerHTML = ''
  })

  it('pergunta numa janela da página, com o foco em Cancelar', async () => {
    const confirm = vi.spyOn(window, 'confirm')
    const wrapper = await abrirJanela()

    expect(confirm).not.toHaveBeenCalled()
    expect(janela()?.textContent).toContain('Remover a saída de 12,5 kg de Ureia agrícola')
    expect(document.activeElement).toBe(botao('Cancelar'))
    wrapper.unmount()
  })

  it('Cancelar e Esc fecham sem remover', async () => {
    const wrapper = await abrirJanela()
    botao('Cancelar').click()
    await flushPromises()
    expect(janela()).toBeNull()

    await wrapper.findAll('button').find((b) => b.text() === 'Remover')!.trigger('click')
    await flushPromises()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()
    expect(janela()).toBeNull()
    expect(api.removerMovimentacao).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('remove ao confirmar e fecha a janela', async () => {
    vi.mocked(api.removerMovimentacao).mockResolvedValue()
    const wrapper = await abrirJanela()

    botao('Remover').click()
    await flushPromises()

    expect(api.removerMovimentacao).toHaveBeenCalledWith(3)
    expect(janela()).toBeNull()
    wrapper.unmount()
  })

  it('se a API recusar, a explicação aparece na janela, que continua aberta', async () => {
    vi.mocked(api.removerMovimentacao).mockRejectedValue(
      new ApiError(409, { detail: 'A remoção deixaria o estoque negativo.' }),
    )
    const wrapper = await abrirJanela()

    botao('Remover').click()
    await flushPromises()

    expect(janela()?.querySelector('[role="alert"]')?.textContent?.trim()).toBe(
      'A remoção deixaria o estoque negativo.',
    )
    wrapper.unmount()
  })
})
