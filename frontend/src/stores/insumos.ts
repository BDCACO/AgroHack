import { defineStore } from 'pinia'

import { mensagemDeErro } from '@/services/http'
import {
  atualizarInsumo,
  criarInsumo,
  listarInsumos,
  removerInsumo,
} from '@/services/insumos'
import type { Insumo, InsumoEntrada } from '@/types/api'

/** Lista de insumos, compartilhada pelas telas de Insumos e de Movimentações
 * (o formulário de movimentação escolhe o insumo daqui). */
export const useInsumosStore = defineStore('insumos', {
  state: () => ({
    lista: [] as Insumo[],
    carregando: false,
    /** Falha ao CARREGAR a lista. Falha ao salvar volta para quem chamou. */
    erro: null as string | null,
  }),
  actions: {
    async carregar() {
      this.carregando = true
      this.erro = null
      try {
        this.lista = await listarInsumos()
      } catch (falha) {
        this.erro = mensagemDeErro(falha)
      } finally {
        this.carregando = false
      }
    },

    /** Cria (id null) ou atualiza. Lança a falha: o formulário mostra a mensagem. */
    async salvar(id: string | null, dados: InsumoEntrada) {
      if (id === null) await criarInsumo(dados)
      else await atualizarInsumo(id, dados)
      await this.carregar()
    },

    async remover(id: string) {
      await removerInsumo(id)
      await this.carregar()
    },
  },
})
