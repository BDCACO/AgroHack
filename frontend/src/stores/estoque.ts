import { defineStore } from 'pinia'

import * as api from '@/services/estoque'
import { ApiError } from '@/services/http'
import type {
  Alerta,
  Insumo,
  InsumoCadastro,
  Movimentacao,
  MovimentacaoEntrada,
} from '@/types/api'

const ORDEM_GRAVIDADE = { alta: 0, media: 1, baixa: 2 } as const

export function mensagemDeErro(erro: unknown): string {
  return erro instanceof ApiError ? erro.mensagem : 'Erro inesperado. Recarregue a página.'
}

/** Insumos (com a análise que a API calculou) e movimentações. Toda alteração
 * recarrega os insumos: uma movimentação muda estoque, alertas e reposição. */
export const useEstoqueStore = defineStore('estoque', {
  state: () => ({
    insumos: [] as Insumo[],
    movimentacoes: [] as Movimentacao[],
    carregando: false,
    carregado: false,
    erro: null as string | null,
  }),
  getters: {
    /** Alertas de todos os insumos, os mais graves primeiro. */
    alertas(): { insumo: Insumo; alerta: Alerta }[] {
      return this.insumos
        .flatMap((insumo) => insumo.analise.alertas.map((alerta) => ({ insumo, alerta })))
        .sort((a, b) => ORDEM_GRAVIDADE[a.alerta.gravidade] - ORDEM_GRAVIDADE[b.alerta.gravidade])
    },
    insumoPorId(): Map<number, Insumo> {
      return new Map(this.insumos.map((insumo) => [insumo.id, insumo]))
    },
  },
  actions: {
    async carregar() {
      this.carregando = true
      this.erro = null
      try {
        const [insumos, movimentacoes] = await Promise.all([
          api.listarInsumos(),
          api.listarMovimentacoes(),
        ])
        this.insumos = insumos
        this.movimentacoes = movimentacoes
        this.carregado = true
      } catch (erro) {
        this.erro = mensagemDeErro(erro)
      } finally {
        this.carregando = false
      }
    },
    /** Sem `id`, cadastra; com `id`, altera. Erros sobem para o formulário mostrar. */
    async salvarInsumo(dados: InsumoCadastro, id?: number) {
      const salvo =
        id === undefined ? await api.criarInsumo(dados) : await api.atualizarInsumo(id, dados)
      this.insumos = [...this.insumos.filter((i) => i.id !== salvo.id), salvo].sort((a, b) =>
        a.nome.localeCompare(b.nome, 'pt-BR'),
      )
    },
    async registrarMovimentacao(dados: MovimentacaoEntrada) {
      await api.registrarMovimentacao(dados)
      await this.carregar()
    },
    async removerMovimentacao(id: number) {
      await api.removerMovimentacao(id)
      await this.carregar()
    },
    /** Sem `confirmar`, só confere. Quando grava, recarrega: muda estoque e alertas. */
    async importarPlanilha(conteudo: string, confirmar: boolean) {
      const resultado = await api.importarPlanilha(conteudo, confirmar)
      if (resultado.importado) await this.carregar()
      return resultado
    },
  },
})
