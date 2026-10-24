import { defineStore } from 'pinia'

import { ApiError } from '@/services/http'
import * as api from '@/services/sessao'
import type { Usuario } from '@/types/api'

// A abertura do site pergunta à API de quem é o token uma vez só, mesmo com o App e a rota
// pedindo ao mesmo tempo. Por instância da store: cada teste monta a sua.
const inicios = new WeakMap<object, Promise<void>>()

/** Quem está usando o site. Sem login (a API de desenvolvimento, com a autenticação
 * desligada, aceita pedido sem token com os poderes do dono), `usuario` fica null e o site
 * funciona como antes. Com ela ligada, o primeiro pedido volta 401 e o App leva à entrada. */
export const useSessaoStore = defineStore('sessao', {
  state: () => ({
    usuario: null as Usuario | null,
  }),
  getters: {
    /** Cadastrar, remover, importar, baixar o relatório: o dono. Sem login, a API trata o
     * pedido como do dono (desligada) ou o recusa com 401 (ligada); nos dois casos esconder
     * o botão não ajudaria. */
    podeGerir(): boolean {
      return this.usuario === null || this.usuario.papel === 'dono'
    },
  },
  actions: {
    /** Na abertura do site: com um token guardado, descobre de quem é. Token que não vale
     * mais (401) já é tratado pelo cliente HTTP, que leva à entrada. */
    iniciar(): Promise<void> {
      let inicio = inicios.get(this)
      if (!inicio) {
        inicio = (async () => {
          if (!api.lerToken()) return
          try {
            this.usuario = await api.buscarEu()
          } catch (erro) {
            if (erro instanceof ApiError && erro.status === 401) this.limpar()
          }
        })()
        inicios.set(this, inicio)
      }
      return inicio
    },
    async entrar(login: string, senha: string) {
      const { token, usuario } = await api.entrar(login, senha)
      api.guardarToken(token)
      this.usuario = usuario
    },
    /** Encerra no servidor também: o token deixa de valer, mesmo copiado. Se a API não
     * responder, sai assim mesmo deste navegador. */
    async sair() {
      try {
        await api.sair()
      } catch {
        // Sem rede ou sessão já encerrada: o token some daqui de qualquer jeito.
      }
      this.limpar()
    },
    limpar() {
      api.guardarToken(null)
      this.usuario = null
    },
  },
})
