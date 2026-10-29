import { DOMWrapper, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/App.vue'
import { routes } from '@/router'
import * as api from '@/services/compras'
import * as estoque from '@/services/estoque'
import { ApiError } from '@/services/http'
import { useSessaoStore } from '@/stores/sessao'
import type { Fornecedor, Insumo, Pedido, SugestaoDePedido } from '@/types/api'

vi.mock('@/services/health', () => ({
  buscarHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
  buscarReadiness: vi.fn().mockResolvedValue({ status: 'pronto', database: 'ok' }),
}))
vi.mock('@/services/estoque', async (original) => ({
  ...(await original<typeof import('@/services/estoque')>()),
  listarInsumos: vi.fn(),
  listarMovimentacoes: vi.fn().mockResolvedValue([]),
  registrarMovimentacao: vi.fn(),
  buscarResumo: vi.fn().mockRejectedValue(new Error('sem resumo aqui')),
}))
vi.mock('@/services/talhoes', () => ({ listarTalhoes: vi.fn().mockResolvedValue([]) }))
vi.mock('@/services/compras', () => ({
  listarFornecedores: vi.fn(),
  buscarFornecedor: vi.fn(),
  criarFornecedor: vi.fn(),
  atualizarFornecedor: vi.fn(),
  removerFornecedor: vi.fn(),
  listarPedidos: vi.fn(),
  sugerirPedido: vi.fn(),
  criarPedido: vi.fn(),
  atualizarPedido: vi.fn(),
  cancelarPedido: vi.fn(),
  receberPedido: vi.fn(),
}))

const ureia: Insumo = {
  id: 1,
  nome: 'Ureia agrícola',
  unidade: 'kg',
  estoque_minimo: 300,
  prazo_reposicao_dias: 10,
  embalagem: 50,
  pedido_minimo: null,
  carencia_dias: 0,
  custo_medio: 3.16,
  valor_em_estoque: 316,
  demonstracao: false,
  estoque_atual: 100,
  analise: { consumo_diario: 12, cobertura_dias: 8, alertas: [], reposicao: null, limitacoes: [] },
}
const agro: Fornecedor = {
  id: 7,
  nome: 'Agro Ariquemes',
  contato: 'Seu Antônio',
  telefone: '(69) 99999-0000',
  cidade: 'Ariquemes',
  observacao: null,
  ativo: true,
  demonstracao: false,
}
const antiga: Fornecedor = { ...agro, id: 8, nome: 'Revenda Antiga', ativo: false, telefone: null }

function pedido(id: number, mudancas: Partial<Pedido> = {}): Pedido {
  return {
    id,
    fornecedor_id: 7,
    fornecedor: 'Agro Ariquemes',
    situacao: 'aberto',
    feito_em: '2026-10-20',
    previsto_para: '2026-10-30',
    observacao: null,
    usuario_id: 1,
    feito_por: 'Dona Maria',
    atrasado: false,
    custo_estimado: 2212,
    itens: [
      {
        id: 70 + id,
        insumo_id: 1,
        insumo: 'Ureia agrícola',
        unidade: 'kg',
        quantidade: 700,
        valor_unitario: 3.16,
        quantidade_recebida: 0,
        falta_receber: 700,
      },
    ],
    ...mudancas,
  }
}
const sugestao: SugestaoDePedido = {
  referencia: '2026-10-27',
  dias: 7,
  grupos: [
    {
      fornecedor_id: 7,
      fornecedor: 'Agro Ariquemes',
      custo_estimado: 2212,
      itens: [
        {
          insumo_id: 1,
          insumo: 'Ureia agrícola',
          unidade: 'kg',
          quantidade: 700,
          valor_unitario: 3.16,
          custo_estimado: 2212,
          pedir_em: '2026-10-27',
          pedir_hoje: true,
          justificativa: 'Pedir hoje 14 embalagens de 50 kg.',
        },
      ],
    },
  ],
  limitacoes: [],
}

async function montarEm(caminho: string) {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(caminho)
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return { wrapper, router }
}
const botao = (wrapper: ReturnType<typeof mount>, texto: string) =>
  wrapper.findAll('main button').find((b) => b.text() === texto)
const formularioNaJanela = () =>
  new DOMWrapper(document.querySelector<HTMLElement>('[role="dialog"] [data-teste="formulario-pedido"]')!)

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  document.body.innerHTML = ''
  vi.mocked(estoque.listarInsumos).mockResolvedValue([ureia])
  vi.mocked(api.listarFornecedores).mockResolvedValue([agro, antiga])
  vi.mocked(api.listarPedidos).mockResolvedValue([
    pedido(1, { atrasado: true, previsto_para: '2026-10-20' }),
    pedido(2, { situacao: 'recebido', itens: [{ ...pedido(2).itens[0]!, quantidade_recebida: 700, falta_receber: 0 }] }),
  ])
  vi.mocked(api.sugerirPedido).mockResolvedValue(sugestao)
})

describe('Compras', () => {
  it('mostra os pedidos a caminho, com o atraso, e o filtro troca a lista', async () => {
    const { wrapper } = await montarEm('/compras')

    const pedidos = wrapper.findAll('[data-teste="pedido"]')
    expect(pedidos).toHaveLength(1)
    expect(pedidos[0]!.text()).toContain('Pedido nº 1 · Agro Ariquemes')
    expect(pedidos[0]!.find('[data-teste="atrasado"]').exists()).toBe(true)
    expect(pedidos[0]!.find('[data-teste="situacao"]').text()).toBe('A caminho')

    await wrapper.findAll('[aria-label="Filtrar pedidos"] button').find((b) => b.text().startsWith('Recebidos'))!.trigger('click')
    expect(wrapper.findAll('[data-teste="pedido"]').map((p) => p.find('h3').text())).toEqual([
      'Pedido nº 2 · Agro Ariquemes',
    ])
    wrapper.unmount()
  })

  it('a sugestão vira pedido: o formulário já vem com a revenda, a quantidade e o preço', async () => {
    vi.mocked(api.criarPedido).mockResolvedValue(pedido(3))
    const { wrapper } = await montarEm('/compras')

    expect(wrapper.find('[data-teste="grupo-sugerido"]').text()).toContain('Pedir hoje')
    await botao(wrapper, 'Fazer este pedido')!.trigger('click')
    // O formulário abre numa janela, que vai para o <body> (Teleport).
    const form = formularioNaJanela()
    expect(document.querySelector('[role="dialog"] h2')?.textContent?.trim()).toBe('Novo pedido de compra')
    expect((form.find('[data-teste="fornecedor"]').element as HTMLSelectElement).value).toBe('7')
    expect(form.find('[data-teste="estimado"]').text()).toMatch(/R\$\s2\.212,00/)
    await form.find('[data-teste="previsao"]').setValue('2026-11-05')
    await form.trigger('submit')
    await flushPromises()

    expect(api.criarPedido).toHaveBeenCalledWith(
      expect.objectContaining({
        fornecedor_id: 7,
        previsto_para: '2026-11-05',
        itens: [{ insumo_id: 1, quantidade: 700, valor_unitario: 3.16 }],
      }),
    )
    expect(wrapper.find('[data-teste="aviso"]').text()).toContain('Pedido nº 3 feito.')
    expect(document.querySelector('[role="dialog"]')).toBeNull()
    // Pedido feito muda o "a caminho" do insumo: o estoque recarrega.
    expect(estoque.listarInsumos).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('no novo pedido, o fornecedor desativado não aparece para escolher', async () => {
    const { wrapper } = await montarEm('/compras')

    await botao(wrapper, 'Novo pedido')!.trigger('click')
    const opcoes = formularioNaJanela().findAll('[data-teste="fornecedor"] option').map((o) => o.text())
    expect(opcoes).toEqual(['Sem fornecedor cadastrado', 'Agro Ariquemes'])
    wrapper.unmount()
  })

  it('a lixeira tira a linha do pedido, e não deixa tirar a última', async () => {
    const { wrapper } = await montarEm('/compras')

    await botao(wrapper, 'Novo pedido')!.trigger('click')
    const form = formularioNaJanela()
    expect(form.find('[data-teste="tirar-item"]').attributes('disabled')).toBeDefined()
    await form.findAll('button').find((b) => b.text() === '+ Outro insumo')!.trigger('click')
    const lixeiras = form.findAll('[data-teste="tirar-item"]')
    expect(lixeiras.map((b) => b.attributes('aria-label'))).toEqual(['Tirar o item 1', 'Tirar o item 2'])

    await lixeiras[1]!.trigger('click')
    expect(form.findAll('[data-teste="linha-pedido"]')).toHaveLength(1)
    wrapper.unmount()
  })

  it('o pedido novo fecha com Cancelar ou Esc, sem pedir nada à API', async () => {
    const { wrapper } = await montarEm('/compras')

    await botao(wrapper, 'Novo pedido')!.trigger('click')
    await formularioNaJanela().findAll('button').find((b) => b.text() === 'Cancelar')!.trigger('click')
    expect(document.querySelector('[role="dialog"]')).toBeNull()

    await botao(wrapper, 'Novo pedido')!.trigger('click')
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()
    expect(document.querySelector('[role="dialog"]')).toBeNull()
    expect(api.criarPedido).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('receber lança o que chegou, linha por linha, e mostra os avisos da API', async () => {
    vi.mocked(api.receberPedido).mockResolvedValue({
      pedido: pedido(1, { situacao: 'parcial' }),
      movimentacoes: [{ id: 90, insumo_id: 1, tipo: 'entrada', data: '2026-10-27', quantidade: 500, validade: null }],
      avisos: ['Chegaram 500 kg de 700 kg pedidos.'],
    })
    const { wrapper } = await montarEm('/compras')

    await wrapper.find('[aria-label="Receber o pedido nº 1"]').trigger('click')
    const linha = document.querySelector('[data-teste="linha-recebimento"]')!
    const quantidade = linha.querySelector<HTMLInputElement>('input[type="number"]')!
    expect(quantidade.value).toBe('700')
    quantidade.value = '500'
    quantidade.dispatchEvent(new Event('input'))
    document.querySelector('[data-teste="receber"]')!.dispatchEvent(new Event('submit'))
    await flushPromises()

    expect(api.receberPedido).toHaveBeenCalledWith(1, {
      data: expect.any(String),
      itens: [{ item_id: 71, quantidade: 500, validade: null, valor_unitario: null }],
    })
    expect(wrapper.find('[data-teste="aviso"]').text()).toContain('1 entrada lançada no estoque')
    expect(wrapper.find('[data-teste="avisos-recebimento"]').text()).toBe('Chegaram 500 kg de 700 kg pedidos.')
    wrapper.unmount()
  })

  it('cancelar pede confirmação e manda para a API', async () => {
    vi.mocked(api.cancelarPedido).mockResolvedValue(pedido(1, { situacao: 'cancelado' }))
    const { wrapper } = await montarEm('/compras')

    await wrapper.find('[aria-label="Cancelar o pedido nº 1"]').trigger('click')
    expect(api.cancelarPedido).not.toHaveBeenCalled()
    document.querySelector<HTMLButtonElement>('[data-teste="confirmar-cancelamento"]')!.click()
    await flushPromises()

    expect(api.cancelarPedido).toHaveBeenCalledWith(1)
    expect(wrapper.find('[data-teste="aviso"]').text()).toContain('Pedido nº 1 cancelado.')
    wrapper.unmount()
  })

  it('o funcionário recebe a carga, mas não vê a sugestão nem faz, altera ou cancela pedido', async () => {
    useSessaoStore().usuario = { id: 2, nome: 'Zé', login: 'ze', papel: 'funcionario' }
    const { wrapper } = await montarEm('/compras')

    expect(api.sugerirPedido).not.toHaveBeenCalled()
    expect(wrapper.find('[data-teste="sugestao"]').exists()).toBe(false)
    expect(botao(wrapper, 'Novo pedido')).toBeUndefined()
    expect(wrapper.find('[aria-label="Cancelar o pedido nº 1"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="Alterar o pedido nº 1"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="Receber o pedido nº 1"]').exists()).toBe(true)
    wrapper.unmount()
  })
})

describe('Fornecedores', () => {
  it('lista os ativos primeiro, com o link do WhatsApp', async () => {
    const { wrapper } = await montarEm('/compras/fornecedores')

    const cartoes = wrapper.findAll('[data-teste="fornecedor"]')
    expect(cartoes.map((c) => c.find('a').text())).toEqual(['Agro Ariquemes', 'Revenda Antiga'])
    expect(cartoes[0]!.find('a[href^="https://wa.me/"]').attributes('href')).toBe('https://wa.me/5569999990000')
    expect(cartoes[1]!.text()).toContain('Desativado')
    // A aba Compras fica acesa.
    expect(wrapper.find('nav[aria-label="Principal"] a[aria-current="page"]').text()).toBe('Compras')
    wrapper.unmount()
  })

  it('o dono cadastra; campo apagado vai como null', async () => {
    vi.mocked(api.criarFornecedor).mockResolvedValue({ ...agro, id: 9, nome: 'Casa do Adubo' })
    const { wrapper } = await montarEm('/compras/fornecedores')

    await botao(wrapper, 'Novo fornecedor')!.trigger('click')
    const campo = (rotulo: string) =>
      wrapper.findAll('main form label').find((l) => l.text().startsWith(rotulo))!.find('input')
    await campo('Nome').setValue('Casa do Adubo')
    await campo('Cidade').setValue('Cacoal')
    await wrapper.find('main form').trigger('submit')
    await flushPromises()

    expect(api.criarFornecedor).toHaveBeenCalledWith({
      nome: 'Casa do Adubo',
      contato: null,
      telefone: null,
      cidade: 'Cacoal',
      observacao: null,
      ativo: true,
    })
    wrapper.unmount()
  })

  it('fornecedor com compras não se remove: a frase da API aparece na janela', async () => {
    vi.mocked(api.removerFornecedor).mockRejectedValue(
      new ApiError(409, { detail: 'O fornecedor tem compras: desative-o.' }),
    )
    const { wrapper } = await montarEm('/compras/fornecedores')

    await wrapper.find('[aria-label="Remover Agro Ariquemes"]').trigger('click')
    document.querySelector<HTMLButtonElement>('[data-teste="confirmar-remocao"]')!.click()
    await flushPromises()

    expect(document.querySelector('[role="dialog"] [role="alert"]')?.textContent?.trim()).toBe(
      'O fornecedor tem compras: desative-o.',
    )
    wrapper.unmount()
  })

  it('a página do fornecedor mostra o preço pago por insumo e as últimas compras', async () => {
    vi.mocked(api.buscarFornecedor).mockResolvedValue({
      ...agro,
      precos: [
        { insumo_id: 1, insumo: 'Ureia agrícola', unidade: 'kg', fornecedor_id: 7, fornecedor: 'Agro Ariquemes', compras: 2, quantidade: 1500, preco_medio: 3.2 },
      ],
      compras: [
        { id: 5, insumo_id: 1, tipo: 'entrada', data: '2026-10-01', quantidade: 1000, validade: null, valor_unitario: 3, lancado_por: 'Zé' },
      ],
    })
    const { wrapper } = await montarEm('/compras/fornecedores/7')

    expect(api.buscarFornecedor).toHaveBeenCalledWith(7)
    expect(wrapper.find('main h1').text()).toBe('Agro Ariquemes')
    expect(wrapper.find('[data-teste="preco-pago"]').text()).toMatch(/Ureia agrícola\s*2 compras\s*1\.500 kg\s*R\$\s3,20\/kg/)
    expect(wrapper.find('[data-teste="compra"]').text()).toMatch(/01\/10\/2026\s*· por Zé/)
    wrapper.unmount()
  })
})

describe('Compra lançada em Movimentações', () => {
  it('a entrada diz de que fornecedor veio; o desativado não aparece', async () => {
    vi.mocked(estoque.registrarMovimentacao).mockResolvedValue({
      id: 41, insumo_id: 1, tipo: 'entrada', data: '2026-10-27', quantidade: 50, validade: null, fornecedor_id: 7,
    })
    const { wrapper } = await montarEm('/movimentacoes')

    expect(wrapper.find('[data-teste="fornecedor"]').exists()).toBe(false)
    await wrapper.find('input[value="entrada"]').setValue(true)
    const fornecedor = wrapper.find('[data-teste="fornecedor"]')
    expect(fornecedor.findAll('option').map((o) => o.text())).toEqual(['Não informar', 'Agro Ariquemes'])
    await wrapper.find('main select').setValue(1)
    await wrapper.find('input[type="number"]').setValue(50)
    await fornecedor.setValue(7)
    await wrapper.find('main form').trigger('submit')
    await flushPromises()

    expect(estoque.registrarMovimentacao).toHaveBeenCalledWith(
      expect.objectContaining({ tipo: 'entrada', fornecedor_id: 7 }),
    )
    wrapper.unmount()
  })
})
