import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import ImportarPage from '@/pages/ImportarPage.vue'
import { routes } from '@/router'
import * as api from '@/services/estoque'
import { ApiError } from '@/services/http'
import type { ResultadoImportacao } from '@/types/api'

// Parcial: as chamadas à API são falsas, mas a URL do modelo é a de verdade.
vi.mock('@/services/estoque', async (original) => ({
  ...(await original<typeof import('@/services/estoque')>()),
  importarPlanilha: vi.fn(),
  listarInsumos: vi.fn().mockResolvedValue([]),
  listarMovimentacoes: vi.fn().mockResolvedValue([]),
}))

const resumo: ResultadoImportacao = {
  linhas: 2,
  entradas: 1,
  saidas: 1,
  insumos: [{ nome: 'Ureia agrícola', unidade: 'kg', novo: true, entradas: 1000, saidas: 25.5 }],
  primeira_data: '2026-03-02',
  ultima_data: '2026-03-09',
  ja_lancadas: 0,
  erros: [],
  importado: false,
}

async function montarEEscolher(bytes: Uint8Array<ArrayBuffer>, nome = 'estoque.csv') {
  const router = createRouter({ history: createMemoryHistory(), routes })
  const wrapper = mount(ImportarPage, { global: { plugins: [router] } })
  const campo = wrapper.find('[data-teste="arquivo"]')
  const arquivo = new File([bytes], nome, { type: 'text/csv' })
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

    expect(api.importarPlanilha).toHaveBeenCalledWith({ conteudo: 'insumo\nUreia agríc' }, false)
    expect(wrapper.find('[data-teste="previa"]').text()).toContain(
      '2 movimentações: 1 entrada e 1 saída, de 02/03/2026 a 09/03/2026.',
    )
    const total = wrapper.find('[data-teste="total-insumo"]').findAll('td')
    expect(total.map((td) => td.text())).toEqual(['Ureia agrícola novo', '1.000 kg', '25,5 kg'])

    await wrapper.find('[data-teste="previa"] button').trigger('click')
    await flushPromises()

    expect(api.importarPlanilha).toHaveBeenLastCalledWith({ conteudo: 'insumo\nUreia agríc' }, true)
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

  it('se o confirmar falha, não oferece o mesmo botão: confere de novo', async () => {
    vi.mocked(api.importarPlanilha)
      .mockResolvedValueOnce(resumo)
      .mockRejectedValueOnce(new ApiError(null))
      .mockResolvedValueOnce({ ...resumo, ja_lancadas: 2 })
    const wrapper = await montarEEscolher(new TextEncoder().encode('qualquer'))

    await wrapper.find('[data-teste="previa"] button').trigger('click')
    await flushPromises()

    // Sem resposta, o servidor pode ter gravado: outro clique importaria em dobro.
    expect(wrapper.find('[data-teste="previa"]').exists()).toBe(false)
    await wrapper.find('[data-teste="conferir-de-novo"]').trigger('click')
    await flushPromises()
    expect(api.importarPlanilha).toHaveBeenLastCalledWith({ conteudo: 'qualquer' }, false)
    expect(wrapper.find('[data-teste="ja-lancadas"]').exists()).toBe(true)
  })

  it('planilha do Excel vai inteira, em base64', async () => {
    vi.mocked(api.importarPlanilha).mockResolvedValueOnce(resumo)

    await montarEEscolher(new TextEncoder().encode('PK planilha'), 'Estoque.XLSX')

    // O FileReader responde fora da fila de microtarefas: espera a chamada chegar.
    await vi.waitFor(() =>
      expect(api.importarPlanilha).toHaveBeenCalledWith({ xlsx: btoa('PK planilha') }, false),
    )
  })

  it.each([
    ['estoque.xls', 'Pasta de Trabalho do Excel (.xlsx)'],
    ['estoque.ods', 'salve como Excel 2007-365 (.xlsx)'],
    ['estoque.numbers', 'Exportar para → Excel'],
    ['foto.jpg', 'Formato não reconhecido'],
  ])('%s nem é enviado: a tela diz o que fazer', async (nome, orientacao) => {
    const wrapper = await montarEEscolher(new TextEncoder().encode('x'), nome)

    expect(api.importarPlanilha).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain(orientacao)
  })

  it('o link do modelo aponta para a planilha que a API gera', () => {
    const router = createRouter({ history: createMemoryHistory(), routes })
    const wrapper = mount(ImportarPage, { global: { plugins: [router] } })

    expect(wrapper.find('[data-teste="modelo-xlsx"]').attributes('href')).toBe(
      '/api/v1/importacoes/modelo.xlsx',
    )
  })
})

describe('ImportarPage, planilha toda já lançada', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('não convida a importar: só "mesmo assim", com confirmação', async () => {
    vi.mocked(api.importarPlanilha).mockReset().mockResolvedValueOnce({ ...resumo, ja_lancadas: 2 })
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const wrapper = await montarEEscolher(new TextEncoder().encode('qualquer'))

    const botoes = wrapper.findAll('[data-teste="previa"] button')
    expect(botoes.map((b) => b.text())).toEqual(['Importar mesmo assim (duplica tudo)'])
    await botoes[0]!.trigger('click')

    expect(confirmar).toHaveBeenCalledOnce()
    expect(api.importarPlanilha).toHaveBeenCalledOnce() // recusou: nada foi gravado
  })
})
