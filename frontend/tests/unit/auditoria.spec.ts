import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/App.vue'
import { dadosLegiveis } from '@/auditoriaLegivel'
import { routes } from '@/router'
import { listarEventos } from '@/services/auditoria'
import { useSessaoStore } from '@/stores/sessao'
import type { EventoDeAuditoria, Usuario } from '@/types/api'

vi.mock('@/services/health', () => ({
  buscarHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
  buscarReadiness: vi.fn().mockResolvedValue({ status: 'pronto', database: 'ok' }),
}))
vi.mock('@/services/estoque', async (original) => ({
  ...(await original<typeof import('@/services/estoque')>()),
  listarInsumos: vi.fn().mockResolvedValue([]),
  listarMovimentacoes: vi.fn().mockResolvedValue([]),
  buscarResumo: vi.fn().mockRejectedValue(new Error('sem resumo aqui')),
}))
vi.mock('@/services/usuarios', () => ({
  listarUsuarios: vi.fn().mockResolvedValue([
    { id: 1, nome: 'Dona Maria', login: 'maria', papel: 'dono', ativo: true, criado_em: '', bloqueado_ate: null },
  ]),
}))
vi.mock('@/services/auditoria', () => ({ listarEventos: vi.fn() }))

const dono: Usuario = { id: 1, nome: 'Dona Maria', login: 'maria', papel: 'dono' }
const evento = (id: number, mudancas: Partial<EventoDeAuditoria> = {}): EventoDeAuditoria => ({
  id,
  ocorrido_em: '2026-10-27T15:04:00Z',
  usuario_id: 1,
  feito_por: 'Dona Maria',
  acao: 'usuario.criado',
  entidade: 'usuario',
  entidade_id: 2,
  dados: { nome: 'Zé', login: 'ze', papel: 'funcionario' },
  origem: 'api',
  ip: '10.0.0.5',
  dispositivo: 'Navegador',
  ...mudancas,
})

async function montarEm(caminho: string, usuario: Usuario | null = dono) {
  useSessaoStore().usuario = usuario
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(caminho)
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  localStorage.clear()
  vi.mocked(listarEventos).mockResolvedValue({
    eventos: [
      evento(3, {
        acao: 'login.recusado',
        usuario_id: null,
        feito_por: null,
        entidade_id: 1,
        dados: { login: 'maria', motivo: 'senha_incorreta' },
      }),
      evento(2),
      evento(1, {
        acao: 'demo.carregada',
        feito_por: null,
        usuario_id: null,
        origem: 'terminal',
        entidade: null,
        entidade_id: null,
        ip: null,
        dispositivo: null,
        dados: { criados: { insumos: 7 } },
      }),
    ],
    total: 4,
  })
})

describe('Auditoria', () => {
  it('mostra cada registro com a ação em palavras, quem, de onde e o que foi guardado', async () => {
    const { wrapper } = await montarEm('/auditoria')

    expect(listarEventos).toHaveBeenCalledWith({ acao: '', usuario_id: '', desde: '', ate: '' }, 50, 0)
    expect(wrapper.find('[data-teste="contagem"]').text()).toBe('4 registros')
    const registros = wrapper.findAll('[data-teste="evento"]')
    expect(registros[0]!.text()).toContain('Login recusado · usuário nº 1')
    expect(registros[0]!.text()).toContain('Por Sem login · Navegador · IP 10.0.0.5')
    // Em palavras, por padrão: o motivo traduzido, e não o código.
    expect(registros[0]!.find('[data-teste="dados-legiveis"]').text()).toMatch(/Login\s*maria\s*Motivo\s*Senha incorreta/)
    expect(registros[1]!.text()).toContain('Usuário criado · usuário nº 2')
    expect(registros[1]!.text()).toContain('Por Dona Maria')
    // O comando rodado no servidor (make demo) não tem login nem IP.
    expect(registros[2]!.text()).toContain('Por Comando no servidor')
    expect(registros[2]!.find('[data-teste="dados-legiveis"]').text()).toMatch(/Criados\s*Insumos\s*7/)
  })

  it('"Técnico" mostra os dados como a API guardou, e o navegador lembra a escolha', async () => {
    const { wrapper } = await montarEm('/auditoria')
    expect(wrapper.find('[data-teste="formato-legivel"]').attributes('aria-checked')).toBe('true')

    await wrapper.find('[data-teste="formato-tecnico"]').trigger('click')

    const registros = wrapper.findAll('[data-teste="evento"]')
    expect(registros[0]!.find('[data-teste="dados-tecnicos"]').text()).toMatch(/login\s*maria\s*motivo\s*senha_incorreta/)
    expect(registros[2]!.find('[data-teste="dados-tecnicos"]').text()).toContain('{"insumos":7}')
    expect(wrapper.find('[data-teste="dados-legiveis"]').exists()).toBe(false)
    expect(localStorage.getItem('campocerto.auditoria-formato')).toBe('tecnico')
    wrapper.unmount()

    setActivePinia(createPinia())
    const outra = await montarEm('/auditoria')
    expect(outra.wrapper.find('[data-teste="formato-tecnico"]').attributes('aria-checked')).toBe('true')
  })

  it('o filtro por grupo vai para a API, e "Carregar mais" pede a próxima página', async () => {
    const { wrapper } = await montarEm('/auditoria')

    await wrapper.find('[data-teste="filtro-acao"]').setValue('login')
    await flushPromises()
    expect(listarEventos).toHaveBeenLastCalledWith(expect.objectContaining({ acao: 'login' }), 50, 0)

    await wrapper.findAll('main button').find((b) => b.text().startsWith('Carregar mais'))!.trigger('click')
    await flushPromises()
    expect(listarEventos).toHaveBeenLastCalledWith(expect.objectContaining({ acao: 'login' }), 50, 3)
  })

  it('o filtro por pessoa usa a lista de usuários', async () => {
    const { wrapper } = await montarEm('/auditoria')

    await wrapper.find('[data-teste="filtro-usuario"]').setValue(1)
    await flushPromises()
    expect(listarEventos).toHaveBeenLastCalledWith(expect.objectContaining({ usuario_id: 1 }), 50, 0)
  })

  it('só o dono, e só com login: o funcionário e o site sem login voltam ao Painel', async () => {
    const funcionario = await montarEm('/auditoria', { id: 2, nome: 'Zé', login: 'ze', papel: 'funcionario' })
    expect(funcionario.router.currentRoute.value.name).toBe('painel')
    expect(funcionario.wrapper.findAll('aside nav a').map((a) => a.text())).not.toContain('Auditoria')

    setActivePinia(createPinia())
    const semLogin = await montarEm('/auditoria', null)
    expect(semLogin.router.currentRoute.value.name).toBe('painel')
    expect(listarEventos).not.toHaveBeenCalled()
  })
})

describe('Os dados em palavras', () => {
  it('o pedido cancelado: a situação traduzida, as datas e cada item pelo insumo, com o preço em reais', () => {
    const linhas = dadosLegiveis({
      itens: [
        { insumo: 'Sal mineral 80P', insumo_id: 5, quantidade: 500, falta_receber: 500, valor_unitario: 4.8, quantidade_recebida: 0 },
      ],
      feito_em: '2026-10-26',
      fornecedor: 'AgroVet Pioneiro',
      fornecedor_id: 3,
      previsto_para: '2026-11-01',
      situacao_antes: 'aberto',
    })

    expect(linhas.map((l) => l.rotulo)).toEqual(['Itens', 'Pedido em', 'Fornecedor', 'Previsão de chegada', 'Situação antes'])
    expect(linhas.slice(1).map((l) => l.valor)).toEqual(['26/10/2026', 'AgroVet Pioneiro', '01/11/2026', 'A caminho'])
    const item = linhas[0]!.filhos![0]!
    expect(item.rotulo).toBe('Sal mineral 80P')
    expect(item.filhos!.map((l) => `${l.rotulo}: ${l.valor}`)).toEqual([
      'Quantidade: 500',
      'Faltava chegar: 500',
      expect.stringMatching(/^Preço unitário: R\$\s4,80$/),
      'Já tinha chegado: 0',
    ])
  })

  it('a alteração diz só o que mudou, de quanto para quanto; campo desconhecido vem com o nome arrumado', () => {
    const linhas = dadosLegiveis({
      nome: 'Ureia agrícola',
      antes: { estoque_minimo: 100, carencia_dias: null },
      depois: { estoque_minimo: 150, carencia_dias: 0 },
      prazo_novo: true,
    })

    expect(linhas[0]).toEqual({
      rotulo: 'O que mudou',
      filhos: [
        { rotulo: 'Estoque mínimo', valor: '100 → 150' },
        { rotulo: 'Carência (dias)', valor: '— → 0' },
      ],
    })
    expect(linhas.slice(1)).toEqual([
      { rotulo: 'Nome', valor: 'Ureia agrícola' },
      { rotulo: 'Prazo novo', valor: 'Sim' },
    ])
  })
})
