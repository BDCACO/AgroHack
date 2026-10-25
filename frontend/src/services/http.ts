import axios, { AxiosError } from 'axios'

import { lerToken } from './token'

/** Cliente HTTP único do front. Nenhum componente chama axios direto.
 *
 * `baseURL` relativa: front e API vivem na mesma origem (proxy do Vite em dev,
 * reverse proxy em produção), então não há URL de API para configurar.
 */
export const http = axios.create({
  baseURL: '/api/v1',
  timeout: 10_000,
})

/** Erro de chamada à API, já normalizado — quem chama não lida com AxiosError. */
export class ApiError extends Error {
  constructor(
    readonly status: number | null,
    readonly detail?: unknown,
  ) {
    super(status === null ? 'a API não respondeu' : `a API respondeu ${status}`)
    this.name = 'ApiError'
  }

  /** Frase para mostrar na tela: a que a API escreveu (409, 404...), quando há uma.
   * Erro de validação (422) vem como lista técnica do Pydantic — não serve ao usuário. */
  get mensagem(): string {
    if (this.status === null) return 'Sem resposta do servidor. Tente de novo em instantes.'
    const detalhe = (this.detail as { detail?: unknown } | undefined)?.detail
    return typeof detalhe === 'string' ? detalhe : 'Não foi possível concluir. Confira os dados.'
  }
}

// O token da sessão vai em todo pedido.
http.interceptors.request.use((config) => {
  const token = lerToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

/** Quem cuida da sessão perdida (o App: limpa a sessão e leva à tela de entrada). Fica
 * registrado de fora para este módulo não depender do roteador. */
let aoPerderSessao: (() => void) | null = null
export function definirAoPerderSessao(funcao: (() => void) | null) {
  aoPerderSessao = funcao
}

http.interceptors.response.use(
  (resposta) => resposta,
  (erro: unknown) => {
    if (erro instanceof AxiosError) {
      const status = erro.response?.status ?? null
      // 401 = falta o login, ou o token venceu, foi encerrado ou o usuário desativado. No
      // próprio login, 401 é só senha errada: a tela de entrada mostra a frase.
      if (status === 401 && !erro.config?.url?.startsWith('/auth/entrar')) aoPerderSessao?.()
      // Sem `response` = rede caiu, timeout ou proxy sem destino.
      return Promise.reject(new ApiError(status, erro.response?.data))
    }
    return Promise.reject(erro)
  },
)
