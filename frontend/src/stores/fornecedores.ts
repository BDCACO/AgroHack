import { defineStore } from 'pinia'

import * as api from '@/services/compras'
import type { Fornecedor, FornecedorCadastro } from '@/types/api'

import { mensagemDeErro } from './estoque'

/** As revendas: o cadastro, a escolha no pedido e na compra lançada em Movimentações. À
 * parte do estoque: se esta leitura falhar, lançar e consultar seguem funcionando. */
export const useFornecedoresStore = defineStore('fornecedores', {
  state: () => ({
    fornecedores: [] as Fornecedor[],
    carregado: false,
    erro: null as string | null,
  }),
  getters: {
    /** Os que aparecem nas escolhas: o desativado só fica no histórico. */
    ativos(): Fornecedor[] {
      return this.fornecedores.filter((fornecedor) => fornecedor.ativo)
    },
    fornecedorPorId(): Map<number, Fornecedor> {
      return new Map(this.fornecedores.map((fornecedor) => [fornecedor.id, fornecedor]))
    },
  },
  actions: {
    async carregar() {
      this.erro = null
      try {
        this.fornecedores = await api.listarFornecedores()
        this.carregado = true
      } catch (erro) {
        this.erro = mensagemDeErro(erro)
      }
    },
    /** Sem `id`, cadastra; com `id`, altera. Erros sobem para o formulário mostrar. */
    async salvar(dados: FornecedorCadastro, id?: number) {
      if (id === undefined) await api.criarFornecedor(dados)
      else await api.atualizarFornecedor(id, dados)
      await this.carregar()
    },
    async remover(id: number) {
      await api.removerFornecedor(id)
      this.fornecedores = this.fornecedores.filter((fornecedor) => fornecedor.id !== id)
    },
  },
})
