import type { Entrada, Sessao, Usuario } from '@/types/api'

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

/** O próprio nome e o próprio login. O login novo pede a senha atual; os aparelhos continuam. */
export async function alterarMeuPerfil(dados: { nome?: string; login?: string; senha_atual?: string }): Promise<Usuario> {
  const { data } = await http.put<Usuario>('/auth/eu', dados)
  return data
}

/** Troca a própria senha; os outros aparelhos saem, este continua. */
export async function trocarSenha(senhaAtual: string, senhaNova: string): Promise<void> {
  await http.put('/auth/senha', { senha_atual: senhaAtual, senha_nova: senhaNova })
}

export async function listarMinhasSessoes(): Promise<Sessao[]> {
  const { data } = await http.get<Sessao[]>('/auth/sessoes')
  return data
}

export async function encerrarMinhaSessao(id: number): Promise<void> {
  await http.delete(`/auth/sessoes/${id}`)
}

export async function encerrarOutrasSessoes(): Promise<number> {
  const { data } = await http.post<{ encerradas: number }>('/auth/sessoes/encerrar-outras')
  return data.encerradas
}
