import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/App.vue'
import { routes } from '@/router'
import { ApiError } from '@/services/http'
import * as conta from '@/services/sessao'
import { useSessaoStore } from '@/stores/sessao'
import { escolherTema } from '@/tema'
import type { Sessao, Usuario } from '@/types/api'

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
// O calendário de safra (do dono) também está em Configurações.
vi.mock('@/services/configuracao', () => ({
  buscarConfiguracao: vi.fn().mockResolvedValue({ meses_de_safra: [] }),
  salvarConfiguracao: vi.fn(),
}))
vi.mock('@/services/sessao', async (original) => ({
  ...(await original<typeof import('@/services/sessao')>()),
  alterarMeuPerfil: vi.fn(),
  trocarSenha: vi.fn(),
  listarMinhasSessoes: vi.fn(),
  encerrarMinhaSessao: vi.fn(),
  encerrarOutrasSessoes: vi.fn(),
}))

const dono: Usuario = { id: 1, nome: 'Dona Maria', login: 'maria', papel: 'dono' }
const sessao = (id: number, mudancas: Partial<Sessao> = {}): Sessao => ({
  id,
  dispositivo: 'Navegador',
  ip: '10.0.0.5',
  criada_em: '2026-10-20T12:00:00Z',
  ultimo_uso_em: new Date().toISOString(),
  expira_em: '2026-11-20T12:00:00Z',
  atual: false,
  ...mudancas,
})

async function montarEm(caminho: string, usuario: Usuario | null = dono) {
  useSessaoStore().usuario = usuario
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(caminho)
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  // A página vem por import() dinâmico: com a suíte inteira em paralelo, demora mais.
  if (caminho === '/configuracoes') {
    await vi.waitFor(() => expect(wrapper.find('[data-teste="sistema"]').exists()).toBe(true), { timeout: 5000 })
  }
  return { wrapper, router }
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  document.body.innerHTML = ''
  localStorage.clear()
  vi.mocked(conta.listarMinhasSessoes).mockResolvedValue([
    sessao(20, { atual: true }),
    sessao(21, { dispositivo: 'Celular' }),
  ])
})
afterEach(() => escolherTema('claro'))

describe('Configurações', () => {
  it('o menu do perfil, na barra do topo, mostra quem é e leva a Configurações', async () => {
    const { wrapper, router } = await montarEm('/')
    const botao = wrapper.find('[data-teste="abrir-perfil"]')
    expect(botao.attributes('aria-expanded')).toBe('false')
    expect(wrapper.find('[data-teste="menu-perfil"]').exists()).toBe(false)

    await botao.trigger('click')

    expect(botao.attributes('aria-expanded')).toBe('true')
    const menu = wrapper.find('[data-teste="menu-perfil"]')
    expect(menu.text()).toMatch(/Dona Maria\s*maria · Dono/)
    // O foco vai para a primeira opção: dá para seguir pelo teclado.
    expect(document.activeElement).toBe(wrapper.find('[data-teste="ir-perfil"]').element)

    await wrapper.find('[data-teste="ir-perfil"]').trigger('click')
    // Configurações vem por import() dinâmico: a navegação leva mais que um flush.
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('configuracoes'), { timeout: 5000 })
    await flushPromises()
    expect(wrapper.find('[data-teste="menu-perfil"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('o menu do perfil fecha com Esc, devolvendo o foco ao botão, e com o clique fora', async () => {
    const { wrapper } = await montarEm('/')
    const botao = wrapper.find('[data-teste="abrir-perfil"]')

    await botao.trigger('click')
    await wrapper.find('[data-teste="menu-perfil"]').trigger('keydown', { key: 'Escape' })
    expect(wrapper.find('[data-teste="menu-perfil"]').exists()).toBe(false)
    expect(document.activeElement).toBe(botao.element)

    await botao.trigger('click')
    document.body.dispatchEvent(new Event('pointerdown', { bubbles: true }))
    await flushPromises()
    expect(wrapper.find('[data-teste="menu-perfil"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('Minha conta e Sistema, os endereços antigos, levam a Configurações', async () => {
    const { wrapper, router } = await montarEm('/')

    await router.push('/conta')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('configuracoes')
    await router.push('/sistema')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('configuracoes')
    expect(wrapper.findAll('aside nav a').map((a) => a.text())).toContain('Configurações')
    expect(wrapper.findAll('aside nav a').map((a) => a.text())).not.toContain('Sistema')
    wrapper.unmount()
  })

  it('mostra se a API e o banco estão no ar, e verifica de novo', async () => {
    const { wrapper } = await montarEm('/configuracoes')

    const sistema = wrapper.find('[data-teste="sistema"]')
    expect(sistema.text()).toMatch(/API\s*Operando/)
    expect(sistema.text()).toMatch(/Banco de dados\s*Operando/)
    const verificar = sistema.findAll('button').find((b) => b.text().includes('Verificar de novo'))!
    expect(verificar.exists()).toBe(true)
    wrapper.unmount()
  })

  it('o tema escuro vale na hora, e o navegador lembra', async () => {
    const { wrapper } = await montarEm('/configuracoes')
    expect(wrapper.find('[data-teste="tema-claro"]').attributes('aria-checked')).toBe('true')

    await wrapper.find('[data-teste="tema-escuro"]').trigger('click')

    expect(document.documentElement.dataset.tema).toBe('escuro')
    expect(localStorage.getItem('campocerto.tema')).toBe('escuro')
    expect(wrapper.find('[data-teste="tema-escuro"]').attributes('aria-checked')).toBe('true')

    await wrapper.find('[data-teste="tema-claro"]').trigger('click')
    expect(document.documentElement.dataset.tema).toBe('claro')
    wrapper.unmount()
  })

  it('troca o nome sem pedir a senha, e o nome novo aparece na barra do topo', async () => {
    vi.mocked(conta.alterarMeuPerfil).mockResolvedValue({ ...dono, nome: 'Maria da Silva' })
    const { wrapper } = await montarEm('/configuracoes')
    expect(wrapper.find('[data-teste="perfil-senha"]').exists()).toBe(false)

    await wrapper.find('[data-teste="perfil-nome"]').setValue('Maria da Silva')
    await wrapper.find('[data-teste="perfil"]').trigger('submit')
    await flushPromises()

    expect(conta.alterarMeuPerfil).toHaveBeenCalledWith({ nome: 'Maria da Silva' })
    expect(wrapper.find('[data-teste="perfil"] [role="status"]').text()).toBe('Perfil salvo.')
    expect(wrapper.find('[data-teste="sessao"]').text()).toContain('Maria da Silva')
    wrapper.unmount()
  })

  it('aberta pelo endereço, antes de saber quem entrou, o perfil se preenche quando o usuário chega', async () => {
    const { wrapper } = await montarEm('/configuracoes', null)
    expect(conta.listarMinhasSessoes).not.toHaveBeenCalled()

    useSessaoStore().usuario = dono
    await flushPromises()

    expect((wrapper.find('[data-teste="perfil-nome"]').element as HTMLInputElement).value).toBe('Dona Maria')
    expect((wrapper.find('[data-teste="perfil-login"]').element as HTMLInputElement).value).toBe('maria')
    // O login é o mesmo de antes: não aparece o campo da senha para trocá-lo.
    expect(wrapper.find('[data-teste="perfil-senha"]').exists()).toBe(false)
    expect(conta.listarMinhasSessoes).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('o login novo pede a senha atual, e a recusa da API aparece', async () => {
    vi.mocked(conta.alterarMeuPerfil).mockRejectedValue(
      new ApiError(400, { detail: 'A senha atual não confere.' }),
    )
    const { wrapper } = await montarEm('/configuracoes')

    await wrapper.find('[data-teste="perfil-login"]').setValue(' Maria.Silva ')
    await wrapper.find('[data-teste="perfil-senha"]').setValue('errada')
    await wrapper.find('[data-teste="perfil"]').trigger('submit')
    await flushPromises()

    expect(conta.alterarMeuPerfil).toHaveBeenCalledWith({
      nome: 'Dona Maria',
      login: 'maria.silva',
      senha_atual: 'errada',
    })
    expect(wrapper.find('[data-teste="perfil"] [role="alert"]').text()).toBe('A senha atual não confere.')
    wrapper.unmount()
  })

  it('a senha nova repetida diferente nem vai para a API; igual, troca e avisa', async () => {
    vi.mocked(conta.trocarSenha).mockResolvedValue()
    const { wrapper } = await montarEm('/configuracoes')
    const campos = wrapper.findAll('[data-teste="trocar-senha"] input')

    await campos[0]!.setValue('senha-velha')
    await campos[1]!.setValue('senha-nova-1')
    await campos[2]!.setValue('senha-nova-2')
    await wrapper.find('[data-teste="trocar-senha"]').trigger('submit')
    expect(conta.trocarSenha).not.toHaveBeenCalled()
    expect(wrapper.find('[data-teste="trocar-senha"] [role="alert"]').text()).toBe(
      'A senha nova e a repetição não são iguais.',
    )

    await campos[2]!.setValue('senha-nova-1')
    await wrapper.find('[data-teste="trocar-senha"]').trigger('submit')
    await flushPromises()
    expect(conta.trocarSenha).toHaveBeenCalledWith('senha-velha', 'senha-nova-1')
    expect(wrapper.find('[data-teste="trocar-senha"] [role="status"]').text()).toContain('Senha trocada.')
    wrapper.unmount()
  })

  it('a senha atual errada mostra a frase da API', async () => {
    vi.mocked(conta.trocarSenha).mockRejectedValue(new ApiError(400, { detail: 'A senha atual não confere.' }))
    const { wrapper } = await montarEm('/configuracoes')
    const campos = wrapper.findAll('[data-teste="trocar-senha"] input')

    await campos[0]!.setValue('errada')
    await campos[1]!.setValue('senha-nova-1')
    await campos[2]!.setValue('senha-nova-1')
    await wrapper.find('[data-teste="trocar-senha"]').trigger('submit')
    await flushPromises()

    expect(wrapper.find('[data-teste="trocar-senha"] [role="alert"]').text()).toBe('A senha atual não confere.')
    wrapper.unmount()
  })

  it('mostra onde está conectado; este aparelho sem "Encerrar"; sair dos outros diz quantos', async () => {
    vi.mocked(conta.encerrarOutrasSessoes).mockResolvedValue(1)
    const { wrapper } = await montarEm('/configuracoes')

    const aparelhos = wrapper.findAll('[data-teste="sessao-aparelho"]')
    expect(aparelhos[0]!.text()).toContain('Este aparelho')
    expect(aparelhos[0]!.find('button').exists()).toBe(false)
    expect(aparelhos[1]!.find('button').text()).toBe('Encerrar')

    vi.mocked(conta.listarMinhasSessoes).mockResolvedValue([sessao(20, { atual: true })])
    await wrapper.findAll('main button').find((b) => b.text() === 'Sair dos outros aparelhos')!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('1 aparelho saiu.')
    expect(wrapper.findAll('[data-teste="sessao-aparelho"]')).toHaveLength(1)
    wrapper.unmount()
  })

  it('sem login, só o tema e o sistema: não há de quem ser o perfil', async () => {
    const { wrapper } = await montarEm('/configuracoes', null)

    expect(wrapper.find('[data-teste="tema-escuro"]').exists()).toBe(true)
    expect(wrapper.find('[data-teste="sistema"]').exists()).toBe(true)
    expect(wrapper.find('[data-teste="perfil"]').exists()).toBe(false)
    expect(wrapper.find('[data-teste="trocar-senha"]').exists()).toBe(false)
    expect(conta.listarMinhasSessoes).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
