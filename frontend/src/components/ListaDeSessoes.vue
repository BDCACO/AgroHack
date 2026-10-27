<script setup lang="ts">
import { ref } from 'vue'

import { dataBr, haQuanto } from '@/formatos'
import { mensagemDeErro } from '@/stores/estoque'
import type { Sessao } from '@/types/api'

import IconeSvg from './IconeSvg.vue'

const props = defineProps<{
  sessoes: Sessao[]
  /** Encerra um aparelho. A falha (sessão que já venceu) aparece ao lado dele. */
  encerrar: (sessao: Sessao) => Promise<void>
}>()

const encerrando = ref<number | null>(null)
const erro = ref<{ id: number; texto: string } | null>(null)

async function encerrarSessao(sessao: Sessao) {
  encerrando.value = sessao.id
  erro.value = null
  try {
    await props.encerrar(sessao)
  } catch (falha) {
    erro.value = { id: sessao.id, texto: mensagemDeErro(falha) }
  } finally {
    encerrando.value = null
  }
}

const dia = (instante: string) => dataBr(instante.slice(0, 10))
</script>

<template>
  <ul class="divide-y divide-stone-100">
    <li
      v-for="sessao in sessoes"
      :key="sessao.id"
      class="flex items-start gap-3 py-3"
      data-teste="sessao-aparelho"
    >
      <span
        class="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
        :class="sessao.atual ? 'bg-campo-100 text-campo-700' : 'bg-stone-100 text-stone-500'"
        aria-hidden="true"
      >
        <IconeSvg
          nome="aparelho"
          class="h-5 w-5"
        />
      </span>
      <div class="min-w-0 flex-1 text-sm">
        <p class="font-medium text-stone-800">
          <!-- O nome é o que o aparelho disse ser: serve para reconhecer, não prova nada. -->
          {{ sessao.dispositivo ?? 'Aparelho sem nome' }}
          <span
            v-if="sessao.atual"
            class="ml-1 rounded-full bg-campo-50 px-2 py-0.5 text-xs font-semibold text-campo-700 ring-1 ring-campo-600/20 ring-inset"
          >Este aparelho</span>
        </p>
        <p class="text-xs text-stone-500">
          Usado {{ haQuanto(sessao.ultimo_uso_em) }} · entrou em {{ dia(sessao.criada_em) }}<template v-if="sessao.ip">
            · IP {{ sessao.ip }}
          </template>
        </p>
        <p
          v-if="erro?.id === sessao.id"
          role="alert"
          class="mt-1 text-xs text-red-700"
        >
          {{ erro.texto }}
        </p>
      </div>
      <button
        v-if="!sessao.atual"
        type="button"
        class="botao-perigo shrink-0 px-3 py-1.5"
        :disabled="encerrando === sessao.id"
        :aria-label="`Encerrar ${sessao.dispositivo ?? 'aparelho sem nome'}`"
        @click="encerrarSessao(sessao)"
      >
        {{ encerrando === sessao.id ? 'Encerrando…' : 'Encerrar' }}
      </button>
    </li>
  </ul>
</template>
