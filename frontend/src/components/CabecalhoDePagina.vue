<script setup lang="ts">
import { onBeforeUnmount, useSlots, watchEffect } from 'vue'
import { useRoute } from 'vue-router'

import { tituloDaPagina } from '@/tituloDaPagina'

const props = defineProps<{
  titulo: string
  descricao?: string
  /** Linha pequena acima do título (a data, no Painel). */
  sobretitulo?: string
}>()
const slots = useSlots()

// O título visível fica na barra do topo; aqui, o h1 continua para o leitor de tela (é por
// ele que se navega de página em página) e o publica para a barra.
const caminho = useRoute().path
watchEffect(() => (tituloDaPagina.value = { caminho, titulo: props.titulo }))
onBeforeUnmount(() => {
  if (tituloDaPagina.value?.caminho === caminho) tituloDaPagina.value = null
})
</script>

<template>
  <h1 class="sr-only">
    {{ titulo }}
  </h1>
  <header
    v-if="sobretitulo || descricao || slots.acoes"
    class="flex flex-col gap-4 pb-6 sm:flex-row sm:items-end sm:justify-between"
  >
    <div class="min-w-0">
      <p
        v-if="sobretitulo"
        class="text-xs font-semibold tracking-wider text-campo-700 uppercase"
      >
        {{ sobretitulo }}
      </p>
      <p
        v-if="descricao"
        class="mt-1.5 max-w-2xl text-sm text-stone-600 sm:text-base"
      >
        {{ descricao }}
      </p>
    </div>
    <div
      v-if="slots.acoes"
      class="flex shrink-0 flex-wrap gap-2"
    >
      <slot name="acoes" />
    </div>
  </header>
</template>
