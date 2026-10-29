import type { Categoria } from '@/types/api'

import { http } from './http'

export async function listarCategorias(): Promise<Categoria[]> {
  const { data } = await http.get<Categoria[]>('/categorias')
  return data
}

export async function criarCategoria(nome: string): Promise<Categoria> {
  const { data } = await http.post<Categoria>('/categorias', { nome })
  return data
}

export async function renomearCategoria(id: number, nome: string): Promise<Categoria> {
  const { data } = await http.put<Categoria>(`/categorias/${id}`, { nome })
  return data
}

/** Só a categoria sem insumos: com algum, a API recusa (409). */
export async function removerCategoria(id: number): Promise<void> {
  await http.delete(`/categorias/${id}`)
}
