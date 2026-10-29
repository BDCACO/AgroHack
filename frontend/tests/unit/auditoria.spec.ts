import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/App.vue'
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
    expect(registros[0]!.find('dl').text()).toMatch(/login\s*maria\s*motivo\s*senha_incorreta/)
    expect(registros[1]!.text()).toContain('Usuário criado · usuário nº 2')
    expect(registros[1]!.text()).toContain('Por Dona Maria')
    // O comando rodado no servidor (make demo) não tem login nem IP.
    expect(registros[2]!.text()).toContain('Por Comando no servidor')
    expect(registros[2]!.find('dl').text()).toContain('{"insumos":7}')
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
