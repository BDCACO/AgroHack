<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'

import { dadosLegiveis } from '@/auditoriaLegivel'
import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import DadosLegiveis from '@/components/DadosLegiveis.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
import { dataHora } from '@/formatos'
import { listarEventos } from '@/services/auditoria'
import { listarUsuarios } from '@/services/usuarios'
import { mensagemDeErro } from '@/stores/estoque'
import type { EventoDeAuditoria, FiltroDeAuditoria, UsuarioCompleto } from '@/types/api'

// A trilha só se lê: nem o dono apaga ou muda um registro.
const POR_PAGINA = 50

/** A ação em palavras. Código novo, que a tela ainda não conhece, aparece como veio. */
const ACOES: Record<string, string> = {
  'movimentacao.removida': 'Movimentação removida',
  'insumo.removido': 'Insumo removido',
  'insumo.alterado': 'Insumo alterado',
  'talhao.removido': 'Talhão removido',
  'talhao.alterado': 'Talhão alterado',
  'categoria.removida': 'Categoria removida',
  'categoria.alterada': 'Categoria alterada',
  'fornecedor.removido': 'Fornecedor removido',
  'fornecedor.alterado': 'Fornecedor alterado',
  'pedido.alterado': 'Pedido alterado',
  'pedido.cancelado': 'Pedido cancelado',
  'importacao.confirmada': 'Planilha importada',
  'usuario.criado': 'Usuário criado',
  'usuario.alterado': 'Usuário alterado',
  'usuario.senha_redefinida': 'Senha definida pelo dono',
  'usuario.senha_trocada': 'Senha trocada',
  'login.recusado': 'Login recusado',
  'login.bloqueado': 'Login bloqueado',
  'login.limitado': 'Tentativas demais de um IP',
  'sessao.encerrada': 'Aparelho desconectado',
  'sessao.encerradas': 'Aparelhos desconectados',
  'demo.carregada': 'Demonstração carregada',
  'demo.limpa': 'Demonstração apagada',
}
// O filtro por grupo: a API aceita o começo do código ("usuario" pega usuario.*).
const GRUPOS = [
  { valor: '', rotulo: 'Tudo' },
  { valor: 'login', rotulo: 'Logins recusados e bloqueios' },
  { valor: 'usuario', rotulo: 'Usuários e senhas' },
  { valor: 'sessao', rotulo: 'Aparelhos desconectados' },
  { valor: 'movimentacao', rotulo: 'Movimentações removidas' },
  { valor: 'insumo', rotulo: 'Insumos' },
  { valor: 'pedido', rotulo: 'Pedidos' },
  { valor: 'fornecedor', rotulo: 'Fornecedores' },
  { valor: 'talhao', rotulo: 'Talhões' },
  { valor: 'categoria', rotulo: 'Categorias' },
  { valor: 'importacao', rotulo: 'Importações' },
  { valor: 'demo', rotulo: 'Demonstração' },
]
// Sobre o quê: "usuário nº 2", e não um "nº 2" solto, que no login recusado pareceria o login.
const ENTIDADES: Record<string, string> = {
  usuario: 'usuário',
  insumo: 'insumo',
  movimentacao: 'movimentação',
  pedido: 'pedido',
  fornecedor: 'fornecedor',
  talhao: 'talhão',
  categoria: 'categoria',
  sessao: 'sessão',
}
// O que apaga, recusa ou bloqueia salta à vista.
const sensivel = (acao: string) => /removid|cancelado|login\.|senha|encerrada/.test(acao)

const filtro = reactive<Required<FiltroDeAuditoria>>({ acao: '', usuario_id: '', desde: '', ate: '' })
const eventos = ref<EventoDeAuditoria[]>([])
const total = ref(0)
const carregado = ref(false)
const buscando = ref(false)
const erro = ref<string | null>(null)
const usuarios = ref<UsuarioCompleto[]>([])

let pedido = 0
async function buscar(acrescentar = false) {
  const este = ++pedido
  buscando.value = true
  erro.value = null
  try {
    const pagina = await listarEventos({ ...filtro }, POR_PAGINA, acrescentar ? eventos.value.length : 0)
    if (este !== pedido) return
    eventos.value = acrescentar ? [...eventos.value, ...pagina.eventos] : pagina.eventos
    total.value = pagina.total
    carregado.value = true
  } catch (falha) {
    if (este === pedido) erro.value = mensagemDeErro(falha)
  } finally {
    if (este === pedido) buscando.value = false
  }
}
onMounted(async () => {
  await buscar()
  try {
    usuarios.value = await listarUsuarios()
  } catch {
    // Sem a lista, o filtro por pessoa só não aparece.
  }
})
watch(filtro, () => buscar())

// Os dados de cada registro: em palavras, para o dono, ou como a API guardou, para quem vai
// conferir campo a campo. A escolha é deste navegador.
type Formato = 'legivel' | 'tecnico'
const CHAVE_DO_FORMATO = 'campocerto.auditoria-formato'
function lerFormato(): Formato {
  try {
    return localStorage.getItem(CHAVE_DO_FORMATO) === 'tecnico' ? 'tecnico' : 'legivel'
  } catch {
    return 'legivel'
  }
}
const formato = ref<Formato>(lerFormato())
watch(formato, (escolhido) => {
  try {
    localStorage.setItem(CHAVE_DO_FORMATO, escolhido)
  } catch {
    // Sem armazenamento, vale só até recarregar.
  }
})
const FORMATOS: { valor: Formato; rotulo: string }[] = [
  { valor: 'legivel', rotulo: 'Fácil de ler' },
  { valor: 'tecnico', rotulo: 'Técnico' },
]

const quem = (evento: EventoDeAuditoria) =>
  evento.feito_por ?? (evento.origem === 'terminal' ? 'Comando no servidor' : 'Sem login')
/** Cada dado numa linha; o que for lista ou objeto, em JSON curto. */
const valor = (dado: unknown) =>
  dado === null ? '—' : typeof dado === 'object' ? JSON.stringify(dado) : String(dado)
</script>

<template>
  <CabecalhoDePagina
    titulo="Auditoria"
    descricao="O que de sensível aconteceu: quem apagou ou mudou o quê, logins recusados, senhas e aparelhos. Os registros não se apagam."
  />

  <div
    class="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
    role="search"
    aria-label="Filtrar a trilha"
  >
    <label class="flutuante">
      <select
        v-model="filtro.acao"
        class="campo"
        data-teste="filtro-acao"
      >
        <option
          v-for="grupo in GRUPOS"
          :key="grupo.valor"
          :value="grupo.valor"
        >
          {{ grupo.rotulo }}
        </option>
      </select>
      <span class="rotulo">O quê</span>
    </label>
    <label class="flutuante">
      <select
        v-model.number="filtro.usuario_id"
        class="campo"
        data-teste="filtro-usuario"
      >
        <option value="">
          Qualquer pessoa
        </option>
        <option
          v-for="usuario in usuarios"
          :key="usuario.id"
          :value="usuario.id"
        >
          {{ usuario.nome }}
        </option>
      </select>
      <span class="rotulo">Quem</span>
    </label>
    <label class="flutuante">
      <input
        v-model="filtro.desde"
        type="date"
        :max="filtro.ate || undefined"
        class="campo"
        data-teste="filtro-desde"
      >
      <span class="rotulo">De</span>
    </label>
    <label class="flutuante">
      <input
        v-model="filtro.ate"
        type="date"
        :min="filtro.desde || undefined"
        class="campo"
        data-teste="filtro-ate"
      >
      <span class="rotulo">Até</span>
    </label>
  </div>

  <p
    v-if="erro"
    role="alert"
    class="text-sm text-red-700"
  >
    {{ erro }}
  </p>

  <EstadoVazio
    v-else-if="carregado && !eventos.length"
    icone="auditoria"
    titulo="Nenhum registro"
    texto="Nada com esses filtros. Quando alguém apagar, alterar, errar a senha ou desconectar um aparelho, fica registrado aqui."
  />

  <template v-else-if="carregado">
    <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
      <p
        class="text-sm text-stone-600"
        role="status"
        data-teste="contagem"
      >
        {{ total === 1 ? '1 registro' : `${total} registros` }}
      </p>
      <div
        class="flex items-center gap-2 text-sm text-stone-600"
        role="radiogroup"
        aria-label="Como mostrar o que foi registrado"
      >
        <span class="hidden sm:inline">Mostrar os dados:</span>
        <div class="inline-flex rounded-lg bg-stone-100 p-0.5">
          <button
            v-for="opcao in FORMATOS"
            :key="opcao.valor"
            type="button"
            role="radio"
            class="rounded-md px-3 py-1 font-medium transition-colors"
            :class="formato === opcao.valor ? 'bg-white text-stone-900 shadow-sm' : 'text-stone-600 hover:text-stone-900'"
            :aria-checked="formato === opcao.valor"
            :data-teste="`formato-${opcao.valor}`"
            @click="formato = opcao.valor"
          >
            {{ opcao.rotulo }}
          </button>
        </div>
      </div>
    </div>
    <ol class="cartao animate-surgir divide-y divide-stone-100">
      <li
        v-for="evento in eventos"
        :key="evento.id"
        class="p-4"
        data-teste="evento"
      >
        <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <p
            class="font-semibold"
            :class="sensivel(evento.acao) ? 'text-red-800' : 'text-stone-900'"
          >
            {{ ACOES[evento.acao] ?? evento.acao }}
            <span
              v-if="evento.entidade_id !== null"
              class="font-normal text-stone-500"
            >· {{ ENTIDADES[evento.entidade ?? ''] ?? evento.entidade }} nº {{ evento.entidade_id }}</span>
          </p>
          <time
            class="text-sm text-stone-500 tabular-nums"
            :datetime="evento.ocorrido_em"
          >{{ dataHora(evento.ocorrido_em) }}</time>
        </div>
        <p class="mt-0.5 text-sm text-stone-600">
          Por <span class="font-medium text-stone-800">{{ quem(evento) }}</span><template v-if="evento.dispositivo">
            · {{ evento.dispositivo }}
          </template><template v-if="evento.ip">
            · IP {{ evento.ip }}
          </template>
        </p>
        <details
          v-if="Object.keys(evento.dados).length"
          class="mt-2 text-sm"
        >
          <summary class="cursor-pointer text-campo-700">
            Ver o que foi registrado
          </summary>
          <div
            v-if="formato === 'legivel'"
            class="mt-2 rounded-lg bg-stone-50 p-3"
            data-teste="dados-legiveis"
          >
            <DadosLegiveis :linhas="dadosLegiveis(evento.dados)" />
          </div>
          <dl
            v-else
            class="mt-2 grid gap-x-4 gap-y-1 rounded-lg bg-stone-50 p-3 sm:grid-cols-[max-content_1fr]"
            data-teste="dados-tecnicos"
          >
            <template
              v-for="(dado, chave) in evento.dados"
              :key="chave"
            >
              <dt class="font-medium text-stone-600">
                {{ chave }}
              </dt>
              <dd class="font-mono text-xs break-all text-stone-800">
                {{ valor(dado) }}
              </dd>
            </template>
          </dl>
        </details>
      </li>
    </ol>
    <div
      v-if="eventos.length < total"
      class="mt-4 flex justify-center"
    >
      <button
        type="button"
        class="botao-secundario"
        :disabled="buscando"
        @click="buscar(true)"
      >
        {{ buscando ? 'Carregando…' : `Carregar mais (${total - eventos.length})` }}
      </button>
    </div>
  </template>
</template>
