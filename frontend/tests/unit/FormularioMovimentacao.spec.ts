import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import FormularioMovimentacao from '@/components/FormularioMovimentacao.vue'
import { ApiError } from '@/services/http'
import { listarInsumos } from '@/services/insumos'
import { listarMovimentacoes, registrarMovimentacao } from '@/services/movimentacoes'
import { useInsumosStore } from '@/stores/insumos'
import type { Insumo } from '@/types/api'

vi.mock('@/services/insumos', () => ({ listarInsumos: vi.fn() }))
vi.mock('@/services/movimentacoes', () => ({
  listarMovimentacoes: vi.fn(),
  registrarMovimentacao: vi.fn(),
}))

const glifosato: Insumo = {
  id: 'g1',
  nome: 'Glifosato',
  categoria: null,
  unidade: 'L',
  estoque_minimo: 20,
  saldo_atual: 35,
  criado_em: '2026-10-17T00:00:00Z',
}

function montar() {
  useInsumosStore().lista = [glifosato]
  return mount(FormularioMovimentacao, { props: { insumoInicialId: 'g1' } })
}

describe('FormularioMovimentacao', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    vi.mocked(listarInsumos).mockResolvedValue([glifosato])
    vi.mocked(listarMovimentacoes).mockResolvedValue([])
  })

  it('mostra o saldo e a unidade do insumo escolhido', () => {
    const wrapper = montar()

    expect(wrapper.find('[data-teste="saldo-disponivel"]').text()).toBe('Saldo atual: 35 L')
    expect(wrapper.find('label[for="mov-quantidade"]').text()).toBe('Quantidade (L)')
  })

  it('validade só aparece em compra', async () => {
    const wrapper = montar()
    expect(wrapper.find('#mov-validade').exists()).toBe(true)

    await wrapper.find('input[value="retirada"]').setValue()

    expect(wrapper.find('#mov-validade').exists()).toBe(false)
  })

  it('registra uma compra com validade', async () => {
    const wrapper = montar()

    await wrapper.find('#mov-quantidade').setValue('10.5')
    await wrapper.find('#mov-data').setValue('2026-10-01')
    await wrapper.find('#mov-validade').setValue('2027-04-30')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(registrarMovimentacao).toHaveBeenCalledWith({
      insumo_id: 'g1',
      tipo: 'compra',
      quantidade: 10.5,
      data: '2026-10-01',
      validade: '2027-04-30',
      observacao: null,
    })
    expect(wrapper.emitted('salvo')).toHaveLength(1)
  })

  it('validade preenchida antes de trocar para retirada não é enviada', async () => {
    const wrapper = montar()

    await wrapper.find('#mov-validade').setValue('2027-04-30')
    await wrapper.find('input[value="retirada"]').setValue()
    await wrapper.find('#mov-quantidade').setValue('5')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(vi.mocked(registrarMovimentacao).mock.calls[0]![0]).toMatchObject({
      tipo: 'retirada',
      validade: null,
    })
  })

  it('estoque insuficiente mostra a explicação da API e não fecha', async () => {
    vi.mocked(registrarMovimentacao).mockRejectedValue(
      new ApiError(409, {
        codigo: 'ESTOQUE_INSUFICIENTE',
        mensagem: 'Retirada de 50 L maior que o saldo disponível (35 L).',
      }),
    )
    const wrapper = montar()

    await wrapper.find('input[value="retirada"]').setValue()
    await wrapper.find('#mov-quantidade').setValue('50')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').text()).toBe(
      'Retirada de 50 L maior que o saldo disponível (35 L).',
    )
    expect(wrapper.emitted('salvo')).toBeUndefined()
  })
})
