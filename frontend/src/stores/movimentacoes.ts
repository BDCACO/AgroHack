import { defineStore } from 'pinia'

import { mensagemDeErro } from '@/services/http'
import {
  listarMovimentacoes,
  registrarMovimentacao,
  removerMovimentacao,
} from '@/services/movimentacoes'
import type { Movimentacao, MovimentacaoEntrada } from '@/types/api'

import { useInsumosStore } from './insumos'

export const useMovimentacoesStore = defineStore('movimentacoes', {
  state: () => ({
    lista: [] as Movimentacao[],
    /** Insumo filtrado; null = todos. */
    filtroInsumoId: null as string | null,
    carregando: false,
    erro: null as string | null,
  }),
  actions: {
    async carregar() {
      this.carregando = true
      this.erro = null
      try {
        this.lista = await listarMovimentacoes(this.filtroInsumoId ?? undefined)
      } catch (falha) {
        this.erro = mensagemDeErro(falha)
      } finally {
        this.carregando = false
      }
    },

    async filtrar(insumoId: string | null) {
      this.filtroInsumoId = insumoId
      await this.carregar()
    },

    /** Lança a falha (ex.: estoque insuficiente): o formulário mostra a mensagem. */
    async registrar(dados: MovimentacaoEntrada) {
      await registrarMovimentacao(dados)
      await this.recarregarTudo()
    },

    async remover(id: string) {
      await removerMovimentacao(id)
      await this.recarregarTudo()
    },

    // Toda movimentação muda o saldo de um insumo: a lista de insumos também
    // é recarregada, para que nenhuma tela mostre saldo velho.
    async recarregarTudo() {
      await Promise.all([this.carregar(), useInsumosStore().carregar()])
    },
  },
})
