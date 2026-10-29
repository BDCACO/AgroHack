import { AxiosError, AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/App.vue'
import { routes } from '@/router'
import { baixarRelatorio } from '@/services/estoque'
import { http } from '@/services/http'
import { guardarToken, lerToken } from '@/services/token'
import type { Insumo, Usuario } from '@/types/api'

vi.mock('@/services/health', () => ({
  buscarHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
  buscarReadiness: vi.fn().mockResolvedValue({ status: 'pronto', database: 'ok' }),
}))

// A API falsa fica no adaptador do axios: o pedido passa pelo cliente HTTP de verdade, com
// os interceptadores do token e do 401.
type Rota = (config: InternalAxiosRequestConfig) => { status: number; data?: unknown; headers?: Record<string, string> }
let rotas: Record<string, Rota> = {}
const pedidos: InternalAxiosRequestConfig[] = []
const adaptadorOriginal = http.defaults.adapter

function responder(config: InternalAxiosRequestConfig): Promise<AxiosResponse> {
  pedidos.push(config)
  const rota = rotas[`${config.method?.toUpperCase()} ${config.url}`]
  const { status, data, headers } = rota ? rota(config) : { status: 404, data: { detail: 'Não há.' } }
  const resposta = { status, data, headers: headers ?? {}, statusText: '', config }
  if (status < 400) return Promise.resolve(resposta)
  return Promise.reject(new AxiosError('erro', undefined, config, null, resposta))
}

const dono: Usuario = { id: 1, nome: 'Dona Maria', login: 'maria', papel: 'dono' }
const peao: Usuario = { id: 2, nome: 'Zé do Campo', login: 'ze', papel: 'funcionario' }
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

/** A API com a autenticação ligada: sem token válido, 401 em tudo, menos no login. */
function apiComLogin(usuarios: Record<string, Usuario>) {
  const tokens: Record<string, Usuario> = {}
  const logado = (config: InternalAxiosRequestConfig) => {
    const cabecalho = String(AxiosHeaders.from(config.headers).get('Authorization') ?? '')
    return tokens[cabecalho.replace('Bearer ', '')]
  }
  const exige =
    (resposta: (u: Usuario) => { status: number; data?: unknown }): Rota =>
    (config) => {
      const usuario = logado(config)
      return usuario ? resposta(usuario) : { status: 401, data: { detail: 'Entre com o seu login e senha para continuar.' } }
    }
  rotas = {
    'POST /auth/entrar': (config) => {
      const { login, senha } = JSON.parse(config.data as string)
      const usuario = usuarios[login]
      if (!usuario || senha !== 'senha-certa') return { status: 401, data: { detail: 'Login ou senha incorretos.' } }
      tokens[`token-${login}`] = usuario
      return { status: 200, data: { token: `token-${login}`, expira_em: '2026-11-23T00:00:00Z', usuario } }
    },
    'GET /auth/eu': exige((usuario) => ({ status: 200, data: usuario })),
    'POST /auth/sair': exige(() => ({ status: 204 })),
    'GET /insumos': exige(() => ({ status: 200, data: [ureia] })),
    'GET /movimentacoes': exige(() => ({
      status: 200,
      data: [
        {
          id: 9,
          insumo_id: 1,
          tipo: 'saida',
          data: '2026-10-20',
          quantidade: 5,
          validade: null,
          lancado_por: 'Zé do Campo',
        },
      ],
    })),
  }
}

async function montarEm(caminho: string) {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(caminho)
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return { wrapper, router }
}

async function entrarComo(wrapper: ReturnType<typeof mount>, login: string, senha = 'senha-certa') {
  await wrapper.find('input[autocomplete="username"]').setValue(login)
  await wrapper.find('input[type="password"]').setValue(senha)
  await wrapper.find('form').trigger('submit')
  await flushPromises()
}

beforeEach(() => {
  setActivePinia(createPinia())
  http.defaults.adapter = responder
  pedidos.length = 0
  guardarToken(null)
})
afterEach(() => {
  http.defaults.adapter = adaptadorOriginal
  document.body.innerHTML = ''
})

describe('cliente HTTP com sessão', () => {
  it('manda o token guardado em todo pedido, e nada sem ele', async () => {
    rotas = { 'GET /insumos': () => ({ status: 200, data: [] }) }

    await http.get('/insumos')
    guardarToken('abc')
    await http.get('/insumos')

    expect(AxiosHeaders.from(pedidos[0]!.headers).has('Authorization')).toBe(false)
    expect(AxiosHeaders.from(pedidos[1]!.headers).get('Authorization')).toBe('Bearer abc')
  })

  it('o relatório vem pelo cliente HTTP (com o token), com o nome que a API dá', async () => {
    guardarToken('abc')
    rotas = {
      'GET /relatorio.xlsx': () => ({
        status: 200,
        data: new Blob(['xlsx']),
        headers: { 'content-disposition': 'attachment; filename="relatorio-campocerto-2026-10-24.xlsx"' },
      }),
    }
    const criarUrl = vi.fn(() => 'blob:relatorio')
    vi.stubGlobal('URL', { createObjectURL: criarUrl, revokeObjectURL: vi.fn() })
    let baixado = ''
    const clique = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      baixado = this.download
    })

    await baixarRelatorio()

    expect(AxiosHeaders.from(pedidos[0]!.headers).get('Authorization')).toBe('Bearer abc')
    expect(baixado).toBe('relatorio-campocerto-2026-10-24.xlsx')
    clique.mockRestore()
    vi.unstubAllGlobals()
  })
})

describe('login no site', () => {
  it('sem login, leva à entrada; depois de entrar, volta para a página em que estava', async () => {
    apiComLogin({ maria: dono })
    const { wrapper, router } = await montarEm('/insumos')

    // A tela de entrada vem por import() dinâmico: a navegação leva mais que um flush (e,
    // com a suíte inteira em paralelo, mais que o segundo padrão do waitFor).
    await vi.waitFor(() => expect(wrapper.find('input[type="password"]').exists()).toBe(true), { timeout: 5000 })
    expect(router.currentRoute.value.name).toBe('entrar')
    expect(router.currentRoute.value.query.volta).toBe('/insumos')

    await entrarComo(wrapper, 'maria')

    expect(lerToken()).toBe('token-maria')
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/insumos'), { timeout: 5000 })
    await flushPromises()
    expect(wrapper.find('[data-teste="sessao"]').text()).toMatch(/Dona Maria\s*Dono/)
    expect(wrapper.text()).toContain('Ureia agrícola')
  })

  it('senha errada: mostra a frase da API, limpa a senha e não guarda nada', async () => {
    apiComLogin({ maria: dono })
    const { wrapper, router } = await montarEm('/entrar')

    await entrarComo(wrapper, 'maria', 'chute')

    expect(router.currentRoute.value.name).toBe('entrar')
    expect(wrapper.find('[role="alert"]').text()).toBe('Login ou senha incorretos.')
    expect((wrapper.find('input[type="password"]').element as HTMLInputElement).value).toBe('')
    expect(lerToken()).toBeNull()
  })

  it('não segue um "volta" para outro site', async () => {
    apiComLogin({ maria: dono })
    const { wrapper, router } = await montarEm('/entrar?volta=//golpe.example/x')

    await entrarComo(wrapper, 'maria')

    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/'))
  })

  it('com o token guardado, abre direto e sabe quem é', async () => {
    apiComLogin({ maria: dono })
    const { wrapper } = await montarEm('/entrar')
    await entrarComo(wrapper, 'maria')
    wrapper.unmount()
    setActivePinia(createPinia())

    const { wrapper: outra, router } = await montarEm('/movimentacoes')

    expect(router.currentRoute.value.path).toBe('/movimentacoes')
    expect(outra.find('[data-teste="sessao"]').text()).toContain('Dona Maria')
  })

  it('sair encerra a sessão na API, esquece o token e volta à entrada', async () => {
    apiComLogin({ maria: dono })
    const { wrapper, router } = await montarEm('/entrar')
    await entrarComo(wrapper, 'maria')

    await wrapper.find('[data-teste="sessao"] button').trigger('click')
    await flushPromises()

    expect(pedidos.some((p) => p.url === '/auth/sair')).toBe(true)
    expect(lerToken()).toBeNull()
    expect(router.currentRoute.value.name).toBe('entrar')
  })

  it('token que deixou de valer (sessão encerrada em outro lugar) leva à entrada', async () => {
    apiComLogin({ maria: dono })
    guardarToken('token-antigo')

    const { router } = await montarEm('/movimentacoes')

    expect(router.currentRoute.value.name).toBe('entrar')
    expect(lerToken()).toBeNull()
  })
})

describe('o funcionário', () => {
  async function comoFuncionario(caminho: string) {
    apiComLogin({ ze: peao })
    const montado = await montarEm('/entrar')
    await entrarComo(montado.wrapper, 'ze')
    await montado.router.push(caminho)
    await flushPromises()
    return montado
  }

  it('não vê Importar no menu, e o endereço digitado leva ao Painel', async () => {
    const { wrapper, router } = await comoFuncionario('/importar')

    expect(router.currentRoute.value.name).toBe('painel')
    const menu = wrapper.findAll('[data-teste="rotulo-menu"]').map((item) => item.text())
    expect(menu).not.toContain('Importar dados')
    // Nem na barra do celular, nem no "Mais".
    expect(wrapper.findAll('[data-teste="aba"]').map((aba) => aba.text())).not.toContain('Importar')
    await wrapper.find('[data-teste="aba-mais"]').trigger('click')
    const mais = [...document.querySelectorAll('[data-teste="menu-mais"] a')].map((a) => a.textContent)
    expect(mais.join(' ')).toContain('Configurações')
    expect(mais.join(' ')).not.toContain('Importar')
  })

  it('consulta e lança, mas não cadastra, não altera, não remove nem baixa o relatório', async () => {
    const { wrapper, router } = await comoFuncionario('/insumos')
    const textos = () => wrapper.findAll('main button').map((b) => b.text())
    expect(wrapper.text()).toContain('Ureia agrícola')
    expect(textos()).not.toContain('Novo insumo')
    expect(textos()).not.toContain('Alterar')

    await router.push('/movimentacoes')
    await flushPromises()
    expect(wrapper.find('main form button[type="submit"]').text()).toBe('Lançar')
    expect(wrapper.find('[data-teste="movimentacao-celular"]').text()).toContain('por Zé do Campo')
    expect(wrapper.find('main [aria-label^="Remover"]').exists()).toBe(false)
    expect(textos()).not.toContain('Remover')

    await router.push('/')
    await flushPromises()
    expect(wrapper.find('[data-teste="relatorio"]').exists()).toBe(false)
  })
})
