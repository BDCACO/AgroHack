import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import InsumosPage from '@/pages/InsumosPage.vue'
import { ApiError } from '@/services/http'
import { criarInsumo, listarInsumos, removerInsumo } from '@/services/insumos'
import type { Insumo } from '@/types/api'

vi.mock('@/services/insumos', () => ({
  listarInsumos: vi.fn(),
  criarInsumo: vi.fn(),
  atualizarInsumo: vi.fn(),
  removerInsumo: vi.fn(),
}))

const ureia: Insumo = {
  id: 'u1',
  nome: 'Ureia',
  categoria: 'Fertilizante',
  unidade: 'kg',
  estoque_minimo: 100,
  saldo_atual: 1250.5,
  criado_em: '2026-10-17T00:00:00Z',
}

async function montar() {
  const wrapper = mount(InsumosPage, {
    global: { stubs: { teleport: true, RouterLink: true } },
  })
  await flushPromises()
  return wrapper
}

describe('InsumosPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  it('lista os insumos com saldo formatado', async () => {
    vi.mocked(listarInsumos).mockResolvedValue([ureia])

    const wrapper = await montar()

    const linha = wrapper.find('tbody tr')
    expect(linha.text()).toContain('Ureia')
    expect(linha.text()).toContain('Fertilizante')
    expect(linha.text()).toContain('1.250,5 kg')
  })

  it('sem insumos mostra o estado vazio', async () => {
    vi.mocked(listarInsumos).mockResolvedValue([])

    const wrapper = await montar()

    expect(wrapper.text()).toContain('Nenhum insumo cadastrado')
    expect(wrapper.find('table').exists()).toBe(false)
  })

  it('cadastra um insumo e recarrega a lista', async () => {
    vi.mocked(listarInsumos).mockResolvedValueOnce([]).mockResolvedValueOnce([ureia])
    vi.mocked(criarInsumo).mockResolvedValue(ureia)
    const wrapper = await montar()

    await wrapper.find('header button').trigger('click')
    await wrapper.find('#insumo-nome').setValue('Ureia')
    await wrapper.find('#insumo-categoria').setValue('  ')
    await wrapper.find('#insumo-unidade').setValue('kg')
    await wrapper.find('#insumo-minimo').setValue('100')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(criarInsumo).toHaveBeenCalledWith({
      nome: 'Ureia',
      categoria: null,
      unidade: 'kg',
      estoque_minimo: 100,
    })
    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.find('tbody').text()).toContain('Ureia')
  })

  it('mostra no formulário a mensagem de erro da API', async () => {
    vi.mocked(listarInsumos).mockResolvedValue([ureia])
    vi.mocked(criarInsumo).mockRejectedValue(
      new ApiError(409, { codigo: 'INSUMO_DUPLICADO', mensagem: 'Já existe um insumo chamado “Ureia”.' }),
    )
    const wrapper = await montar()

    await wrapper.find('header button').trigger('click')
    await wrapper.find('#insumo-nome').setValue('ureia')
    await wrapper.find('#insumo-unidade').setValue('kg')
    await wrapper.find('#insumo-minimo').setValue('0')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').text()).toBe('Já existe um insumo chamado “Ureia”.')
    expect(wrapper.find('form').exists()).toBe(true)
  })

  it('remoção recusada pela API mantém a janela aberta com o motivo', async () => {
    vi.mocked(listarInsumos).mockResolvedValue([ureia])
    vi.mocked(removerInsumo).mockRejectedValue(
      new ApiError(409, { codigo: 'INSUMO_COM_MOVIMENTACOES', mensagem: 'Este insumo tem movimentações registradas.' }),
    )
    const wrapper = await montar()

    const remover = wrapper.findAll('tbody button').find((b) => b.text() === 'Remover')
    await remover!.trigger('click')
    await wrapper.find('.botao-perigo').trigger('click')
    await flushPromises()

    expect(removerInsumo).toHaveBeenCalledWith('u1')
    expect(wrapper.find('[role="alert"]').text()).toBe('Este insumo tem movimentações registradas.')
  })
})
