import axios, { AxiosError } from 'axios'

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
}

http.interceptors.response.use(
  (resposta) => resposta,
  (erro: unknown) => {
    if (erro instanceof AxiosError) {
      // Sem `response` = rede caiu, timeout ou proxy sem destino.
      return Promise.reject(new ApiError(erro.response?.status ?? null, erro.response?.data))
    }
    return Promise.reject(erro)
  },
)
