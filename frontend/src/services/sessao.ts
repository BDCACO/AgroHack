import type { Entrada, Usuario } from '@/types/api'

import { http } from './http'
import { guardarToken, lerToken } from './token'

export { guardarToken, lerToken }

export async function entrar(login: string, senha: string): Promise<Entrada> {
  const { data } = await http.post<Entrada>('/auth/entrar', {
    login,
    senha,
    dispositivo: 'Navegador',
  })
  return data
}

export async function buscarEu(): Promise<Usuario> {
  const { data } = await http.get<Usuario>('/auth/eu')
  return data
}

export async function sair(): Promise<void> {
  await http.post('/auth/sair')
}
