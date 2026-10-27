import { defineStore } from 'pinia'

import * as api from '@/services/categorias'
import type { Categoria } from '@/types/api'

import { mensagemDeErro } from './estoque'

/** Fertilizante, defensivo, nutrição animal...: o filtro da lista de insumos e a divisão do
 * relatório. Opcional: sem nenhuma, tudo funciona como antes. */
export const useCategoriasStore = defineStore('categorias', {
  state: () => ({
    categorias: [] as Categoria[],
    erro: null as string | null,
  }),
  actions: {
    async carregar() {
      this.erro = null
      try {
        this.categorias = await api.listarCategorias()
      } catch (erro) {
        this.erro = mensagemDeErro(erro)
      }
    },
    /** Erros sobem para a janela mostrar (nome repetido, categoria com insumos). */
    async criar(nome: string) {
      await api.criarCategoria(nome)
      await this.carregar()
    },
    async renomear(id: number, nome: string) {
      await api.renomearCategoria(id, nome)
      await this.carregar()
    },
    async remover(id: number) {
      await api.removerCategoria(id)
      this.categorias = this.categorias.filter((categoria) => categoria.id !== id)
    },
  },
})
