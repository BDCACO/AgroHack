import { defineStore } from 'pinia'

import * as api from '@/services/talhoes'
import type { Talhao, TalhaoCadastro } from '@/types/api'

import { mensagemDeErro } from './estoque'

/** Talhões com a carência e o custo que a API calculou. À parte do estoque: o Painel e
 * Movimentações seguem funcionando se esta leitura falhar. */
export const useTalhoesStore = defineStore('talhoes', {
  state: () => ({
    talhoes: [] as Talhao[],
    carregado: false,
    erro: null as string | null,
  }),
  getters: {
    emCarencia(): Talhao[] {
      return this.talhoes.filter((talhao) => talhao.em_carencia)
    },
    talhaoPorId(): Map<number, Talhao> {
      return new Map(this.talhoes.map((talhao) => [talhao.id, talhao]))
    },
  },
  actions: {
    async carregar() {
      this.erro = null
      try {
        this.talhoes = await api.listarTalhoes()
        this.carregado = true
      } catch (erro) {
        this.erro = mensagemDeErro(erro)
      }
    },
    /** Sem `id`, cadastra; com `id`, altera. Erros sobem para o formulário mostrar. */
    async salvar(dados: TalhaoCadastro, id?: number) {
      if (id === undefined) await api.criarTalhao(dados)
      else await api.atualizarTalhao(id, dados)
      await this.carregar()
    },
    async remover(id: number) {
      await api.removerTalhao(id)
      this.talhoes = this.talhoes.filter((talhao) => talhao.id !== id)
    },
  },
})
