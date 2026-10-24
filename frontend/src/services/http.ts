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

/** Frase para mostrar ao usuário a partir de uma falha de chamada.
 *
 * A mensagem de regra de negócio é escrita pela API (`{codigo, mensagem}`) e
 * mostrada como veio; o front não reescreve regra. Para os demais casos, um
 * texto genérico honesto — nunca o corpo cru da resposta.
 */
export function mensagemDeErro(falha: unknown): string {
  if (!(falha instanceof ApiError)) return 'Algo deu errado. Tente novamente.'
  if (falha.status === null) return 'Não foi possível falar com o servidor. Verifique a conexão.'
  const corpo = falha.detail
  if (corpo !== null && typeof corpo === 'object' && 'mensagem' in corpo) {
    const mensagem = (corpo as { mensagem: unknown }).mensagem
    if (typeof mensagem === 'string' && mensagem.length > 0) return mensagem
  }
  if (falha.status === 422) return 'Confira os campos preenchidos.'
  return 'O servidor não conseguiu concluir a operação. Tente novamente.'
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
