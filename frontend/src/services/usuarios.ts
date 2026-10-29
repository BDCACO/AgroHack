import type { Sessao, UsuarioAlteracao, UsuarioCadastro, UsuarioCompleto } from '@/types/api'

import { http } from './http'

// Tudo aqui é do dono, e só com login: a API recusa o resto.

export async function listarUsuarios(): Promise<UsuarioCompleto[]> {
  const { data } = await http.get<UsuarioCompleto[]>('/usuarios')
  return data
}

export async function criarUsuario(dados: UsuarioCadastro): Promise<UsuarioCompleto> {
  const { data } = await http.post<UsuarioCompleto>('/usuarios', dados)
  return data
}

export async function alterarUsuario(id: number, dados: UsuarioAlteracao): Promise<UsuarioCompleto> {
  const { data } = await http.put<UsuarioCompleto>(`/usuarios/${id}`, dados)
  return data
}

/** Derruba as sessões dele e desfaz o bloqueio por senhas erradas. */
export async function redefinirSenha(id: number, senhaNova: string): Promise<void> {
  await http.put(`/usuarios/${id}/senha`, { senha_nova: senhaNova })
}

export async function listarSessoesDe(id: number): Promise<Sessao[]> {
  const { data } = await http.get<Sessao[]>(`/usuarios/${id}/sessoes`)
  return data
}

export async function encerrarSessaoDe(id: number, sessaoId: number): Promise<void> {
  await http.delete(`/usuarios/${id}/sessoes/${sessaoId}`)
}

export async function encerrarSessoesDe(id: number): Promise<number> {
  const { data } = await http.post<{ encerradas: number }>(`/usuarios/${id}/sessoes/encerrar`)
  return data.encerradas
}
