import { describe, expect, it } from 'vitest'

import { ApiError, mensagemDeErro } from '@/services/http'

describe('mensagemDeErro', () => {
  it('mostra a mensagem de regra de negócio escrita pela API', () => {
    const falha = new ApiError(409, { codigo: 'ESTOQUE_INSUFICIENTE', mensagem: 'Retirada maior que o saldo.' })

    expect(mensagemDeErro(falha)).toBe('Retirada maior que o saldo.')
  })

  it('validação 422 do FastAPI vira um pedido para conferir os campos', () => {
    const falha = new ApiError(422, { detail: [{ loc: ['body', 'nome'], msg: 'x' }] })

    expect(mensagemDeErro(falha)).toBe('Confira os campos preenchidos.')
  })

  it('sem resposta do servidor fala de conexão', () => {
    expect(mensagemDeErro(new ApiError(null))).toMatch(/servidor/)
  })

  it('nunca mostra corpo cru de erro 500', () => {
    const falha = new ApiError(500, 'Traceback (most recent call last): ...')

    expect(mensagemDeErro(falha)).not.toContain('Traceback')
  })

  it('erro que não veio da API ganha texto genérico', () => {
    expect(mensagemDeErro(new TypeError('x'))).toBe('Algo deu errado. Tente novamente.')
  })
})
