<script setup lang="ts">
defineProps<{
  titulo: string
  descricao?: string
  /** Linha pequena acima do título (a data, no Painel). */
  sobretitulo?: string
}>()
</script>

<template>
  <header class="flex flex-col gap-4 pb-6 sm:flex-row sm:items-end sm:justify-between">
    <div class="min-w-0">
      <p
        v-if="sobretitulo"
        class="text-xs font-semibold tracking-wider text-campo-700 uppercase"
      >
        {{ sobretitulo }}
      </p>
      <h1 class="text-2xl font-bold text-campo-950 sm:text-3xl">
        {{ titulo }}
      </h1>
      <p
        v-if="descricao"
        class="mt-1.5 max-w-2xl text-sm text-stone-600 sm:text-base"
      >
        {{ descricao }}
      </p>
    </div>
    <div
      v-if="$slots.acoes"
      class="flex shrink-0 flex-wrap gap-2"
    >
      <slot name="acoes" />
    </div>
  </header>
</template>
