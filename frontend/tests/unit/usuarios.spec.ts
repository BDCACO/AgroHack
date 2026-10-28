import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/App.vue'
import { routes } from '@/router'
import { ApiError } from '@/services/http'
import * as conta from '@/services/sessao'
import * as api from '@/services/usuarios'
import { useSessaoStore } from '@/stores/sessao'
import type { Sessao, Usuario, UsuarioCompleto } from '@/types/api'

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
  listarUsuarios: vi.fn(),
  criarUsuario: vi.fn(),
  alterarUsuario: vi.fn(),
  redefinirSenha: vi.fn(),
  listarSessoesDe: vi.fn(),
  encerrarSessaoDe: vi.fn(),
  encerrarSessoesDe: vi.fn(),
}))
vi.mock('@/services/sessao', async (original) => ({
  ...(await original<typeof import('@/services/sessao')>()),
  trocarSenha: vi.fn(),
  listarMinhasSessoes: vi.fn(),
  encerrarMinhaSessao: vi.fn(),
  encerrarOutrasSessoes: vi.fn(),
}))

const dono: Usuario = { id: 1, nome: 'Dona Maria', login: 'maria', papel: 'dono' }
const completo = (usuario: Usuario, mudancas: Partial<UsuarioCompleto> = {}): UsuarioCompleto => ({
  ...usuario,
  ativo: true,
  criado_em: '2026-10-01T12:00:00Z',
  bloqueado_ate: null,
  ...mudancas,
})
const ze = completo({ id: 2, nome: 'Zé do Campo', login: 'ze', papel: 'funcionario' })
const ana = completo(
  { id: 3, nome: 'Ana', login: 'ana', papel: 'funcionario' },
  { bloqueado_ate: '2999-01-01T12:00:00Z' },
)
const beto = completo({ id: 4, nome: 'Beto', login: 'beto', papel: 'funcionario' }, { ativo: false })

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
  return { wrapper, router }
}

const linha = (wrapper: ReturnType<typeof mount>, nome: string) =>
  wrapper.findAll('[data-teste="usuario"]').find((l) => l.text().includes(nome))!

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  document.body.innerHTML = ''
  vi.mocked(api.listarUsuarios).mockResolvedValue([completo(dono), ze, ana, beto])
})

describe('Usuários', () => {
  it('lista cada um com o papel, quem é você, quem está bloqueado e quem está desativado', async () => {
    const { wrapper } = await montarEm('/usuarios')

    expect(wrapper.findAll('[data-teste="usuario"]')).toHaveLength(4)
    expect(linha(wrapper, 'Dona Maria').text()).toContain('(você)')
    expect(linha(wrapper, 'Dona Maria').text()).not.toContain('Desativar')
    expect(linha(wrapper, 'Zé do Campo').text()).toContain('ze · Funcionário')
    expect(linha(wrapper, 'Ana').text()).toContain('Bloqueado até')
    expect(linha(wrapper, 'Beto').text()).toContain('Desativado')
    expect(linha(wrapper, 'Beto').text()).toContain('Reativar')
    wrapper.unmount()
  })

  it('o dono cadastra um funcionário com login e senha inicial', async () => {
    vi.mocked(api.criarUsuario).mockResolvedValue(completo({ id: 5, nome: 'Joca', login: 'joca', papel: 'funcionario' }))
    const { wrapper } = await montarEm('/usuarios')

    await wrapper.findAll('main button').find((b) => b.text() === 'Novo usuário')!.trigger('click')
    const campo = (rotulo: string) =>
      wrapper.findAll('main form label').find((l) => l.text().startsWith(rotulo))!.find('input')
    await campo('Nome').setValue('Joca')
    await campo('Login').setValue(' Joca ')
    await campo('Senha inicial').setValue('senha-forte-1')
    await wrapper.find('main form').trigger('submit')
    await flushPromises()

    expect(api.criarUsuario).toHaveBeenCalledWith({
      nome: 'Joca',
      login: 'joca',
      senha: 'senha-forte-1',
      papel: 'funcionario',
    })
    expect(api.listarUsuarios).toHaveBeenCalledTimes(2)
    expect(wrapper.find('main form').exists()).toBe(false)
    wrapper.unmount()
  })

  it('desativar pede confirmação, e a recusa da API aparece na janela', async () => {
    vi.mocked(api.alterarUsuario).mockRejectedValue(
      new ApiError(409, { detail: 'O último dono ativo não se desativa.' }),
    )
    const { wrapper } = await montarEm('/usuarios')

    await wrapper.find('[aria-label="Desativar Zé do Campo"]').trigger('click')
    expect(api.alterarUsuario).not.toHaveBeenCalled()
    document.querySelector<HTMLButtonElement>('[data-teste="confirmar-desativacao"]')!.click()
    await flushPromises()

    expect(api.alterarUsuario).toHaveBeenCalledWith(2, { ativo: false })
    expect(document.querySelector('[role="dialog"] [role="alert"]')?.textContent?.trim()).toBe(
      'O último dono ativo não se desativa.',
    )
    wrapper.unmount()
  })

  it('a nova senha vai para a API e a tela avisa que os aparelhos dele saíram', async () => {
    vi.mocked(api.redefinirSenha).mockResolvedValue()
    const { wrapper } = await montarEm('/usuarios')

    await wrapper.find('[aria-label="Nova senha para Ana"]').trigger('click')
    const campo = document.querySelector<HTMLInputElement>('[data-teste="nova-senha"] input')!
    campo.value = 'outra-senha-1'
    campo.dispatchEvent(new Event('input'))
    document.querySelector<HTMLFormElement>('[data-teste="nova-senha"]')!.dispatchEvent(new Event('submit'))
    await flushPromises()

    expect(api.redefinirSenha).toHaveBeenCalledWith(3, 'outra-senha-1')
    expect(wrapper.text()).toContain('Senha nova de Ana definida.')
    wrapper.unmount()
  })

  it('os aparelhos de alguém se encerram um a um, sem desativá-lo', async () => {
    vi.mocked(api.listarSessoesDe).mockResolvedValue([
      sessao(10, { dispositivo: 'Celular do Zé' }),
      sessao(11, { dispositivo: 'Navegador' }),
    ])
    vi.mocked(api.encerrarSessaoDe).mockResolvedValue()
    const { wrapper } = await montarEm('/usuarios')

    await wrapper.find('[aria-label="Aparelhos de Zé do Campo"]').trigger('click')
    await flushPromises()
    expect(document.querySelectorAll('[data-teste="sessao-aparelho"]')).toHaveLength(2)
    document.querySelector<HTMLButtonElement>('[aria-label="Encerrar Celular do Zé"]')!.click()
    await flushPromises()

    expect(api.encerrarSessaoDe).toHaveBeenCalledWith(2, 10)
    expect(api.alterarUsuario).not.toHaveBeenCalled()
    expect(document.querySelectorAll('[data-teste="sessao-aparelho"]')).toHaveLength(1)
    wrapper.unmount()
  })

  it('o funcionário não vê a tela: some do menu, e o endereço leva ao Painel', async () => {
    const { wrapper, router } = await montarEm('/usuarios', { ...ze })

    expect(router.currentRoute.value.name).toBe('painel')
    expect(wrapper.findAll('aside nav a').map((a) => a.text())).not.toContain('Usuários')
    wrapper.unmount()
  })

  it('sem login (autenticação desligada), não há tela de usuários', async () => {
    const { wrapper, router } = await montarEm('/usuarios', null)

    expect(router.currentRoute.value.name).toBe('painel')
    expect(wrapper.findAll('aside nav a').map((a) => a.text())).not.toContain('Usuários')
    wrapper.unmount()
  })
})

describe('Minha conta', () => {
  beforeEach(() => {
    vi.mocked(conta.listarMinhasSessoes).mockResolvedValue([
      sessao(20, { atual: true }),
      sessao(21, { dispositivo: 'Celular' }),
    ])
  })

  it('o nome no menu leva à conta, que mostra quem é e onde está conectado', async () => {
    const { wrapper, router } = await montarEm('/')

    expect(wrapper.find('aside a[href="/conta"]').text()).toContain('Dona Maria')
    await router.push('/conta')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('conta')
    expect(wrapper.find('[data-teste="quem"]').text()).toBe('Login maria · Dono')
    const aparelhos = wrapper.findAll('[data-teste="sessao-aparelho"]')
    expect(aparelhos[0]!.text()).toContain('Este aparelho')
    // Este aparelho não tem "Encerrar": para ele, é "Sair".
    expect(aparelhos[0]!.find('button').exists()).toBe(false)
    expect(aparelhos[1]!.find('button').text()).toBe('Encerrar')
    wrapper.unmount()
  })

  it('a senha nova repetida diferente nem vai para a API; igual, troca e avisa', async () => {
    vi.mocked(conta.trocarSenha).mockResolvedValue()
    const { wrapper } = await montarEm('/conta')
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
    const { wrapper } = await montarEm('/conta')
    const campos = wrapper.findAll('[data-teste="trocar-senha"] input')

    await campos[0]!.setValue('errada')
    await campos[1]!.setValue('senha-nova-1')
    await campos[2]!.setValue('senha-nova-1')
    await wrapper.find('[data-teste="trocar-senha"]').trigger('submit')
    await flushPromises()

    expect(wrapper.find('[data-teste="trocar-senha"] [role="alert"]').text()).toBe('A senha atual não confere.')
    wrapper.unmount()
  })

  it('sair dos outros aparelhos diz quantos saíram', async () => {
    vi.mocked(conta.encerrarOutrasSessoes).mockResolvedValue(1)
    const { wrapper } = await montarEm('/conta')

    vi.mocked(conta.listarMinhasSessoes).mockResolvedValue([sessao(20, { atual: true })])
    await wrapper.findAll('main button').find((b) => b.text() === 'Sair dos outros aparelhos')!.trigger('click')
    await flushPromises()

    expect(conta.encerrarOutrasSessoes).toHaveBeenCalled()
    expect(wrapper.text()).toContain('1 aparelho saiu.')
    expect(wrapper.findAll('[data-teste="sessao-aparelho"]')).toHaveLength(1)
    wrapper.unmount()
  })
})
