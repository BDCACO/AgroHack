import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import ImportarPage from '@/pages/ImportarPage.vue'
import { routes } from '@/router'
import * as api from '@/services/estoque'
import type { ResultadoImportacao } from '@/types/api'

vi.mock('@/services/estoque', () => ({
  importarPlanilha: vi.fn(),
  listarInsumos: vi.fn().mockResolvedValue([]),
  listarMovimentacoes: vi.fn().mockResolvedValue([]),
}))

const resumo: ResultadoImportacao = {
  linhas: 2,
  entradas: 1,
  saidas: 1,
  insumos_novos: ['Ureia agrícola'],
  primeira_data: '2026-03-02',
  ultima_data: '2026-03-09',
  ja_lancadas: 0,
  erros: [],
  importado: false,
}

async function montarEEscolher(bytes: Uint8Array<ArrayBuffer>) {
  const router = createRouter({ history: createMemoryHistory(), routes })
  const wrapper = mount(ImportarPage, { global: { plugins: [router] } })
  const campo = wrapper.find('[data-teste="arquivo"]')
  const arquivo = new File([bytes], 'estoque.csv', { type: 'text/csv' })
  Object.defineProperty(campo.element, 'files', { value: [arquivo] })
  await campo.trigger('change')
  await flushPromises()
  return wrapper
}

describe('ImportarPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.importarPlanilha).mockReset()
  })

  it('confere, mostra o resumo e só grava ao confirmar', async () => {
    vi.mocked(api.importarPlanilha)
      .mockResolvedValueOnce(resumo)
      .mockResolvedValueOnce({ ...resumo, importado: true })
    // "agrícola" em Windows-1252 (í = 0xED), como o Excel em português grava.
    const csv = new Uint8Array([...new TextEncoder().encode('insumo\nUreia agr'), 0xed, 0x63])

    const wrapper = await montarEEscolher(csv)

    expect(api.importarPlanilha).toHaveBeenCalledWith('insumo\nUreia agríc', false)
    expect(wrapper.find('[data-teste="previa"]').text()).toContain(
      '2 movimentações: 1 entrada e 1 saída, de 02/03/2026 a 09/03/2026.',
    )

    await wrapper.find('[data-teste="previa"] button').trigger('click')
    await flushPromises()

    expect(api.importarPlanilha).toHaveBeenLastCalledWith('insumo\nUreia agríc', true)
    expect(api.listarInsumos).toHaveBeenCalled() // recarregou estoque e alertas
    expect(wrapper.find('[data-teste="importado"]').text()).toContain(
      'Importação concluída: 2 movimentações.',
    )
  })

  it('com erros, lista cada um e não oferece importar', async () => {
    vi.mocked(api.importarPlanilha).mockResolvedValueOnce({
      ...resumo,
      erros: ['Linha 3: data no futuro.'],
    })

    const wrapper = await montarEEscolher(new TextEncoder().encode('qualquer'))

    expect(wrapper.find('[data-teste="erros"]').text()).toContain('Linha 3: data no futuro.')
    expect(wrapper.find('[data-teste="previa"]').exists()).toBe(false)
  })
})
