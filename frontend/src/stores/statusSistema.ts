import { defineStore } from 'pinia'

import { buscarHealth, buscarReadiness } from '@/services/health'

export type EstadoServico = 'desconhecido' | 'ok' | 'erro'

/** Situação da API e do banco, vista pelo front. Valida a cadeia
 * navegador → Vite → FastAPI → PostgreSQL de ponta a ponta. */
export const useStatusSistemaStore = defineStore('statusSistema', {
  state: () => ({
    api: 'desconhecido' as EstadoServico,
    banco: 'desconhecido' as EstadoServico,
    verificando: false,
    verificadoEm: null as Date | null,
  }),
  actions: {
    async verificar() {
      this.verificando = true
      try {
        try {
          await buscarHealth()
          this.api = 'ok'
        } catch {
          // API inalcançável: o banco fica "desconhecido", não "erro" — afirmar
          // que ele caiu seria palpite.
          this.api = 'erro'
          this.banco = 'desconhecido'
          return
        }
        try {
          const prontidao = await buscarReadiness()
          this.banco = prontidao.database === 'ok' ? 'ok' : 'erro'
        } catch {
          this.banco = 'erro'
        }
      } finally {
        this.verificando = false
        this.verificadoEm = new Date()
      }
    },
  },
})
