<script setup lang="ts">
defineProps<{
  titulo: string
  descricao?: string
  /** Linha pequena acima do título (a data, no Painel). */
  sobretitulo?: string
}>()
</script>

<template>
  <header class="mb-8 flex flex-col gap-5 border-b border-linha pb-6 sm:flex-row sm:items-end sm:justify-between">
    <div class="min-w-0">
      <p
        v-if="sobretitulo"
        class="mb-1 text-sm text-tinta-3 first-letter:uppercase"
      >
        {{ sobretitulo }}
      </p>
      <h1 class="font-serif text-[2rem] leading-tight font-medium tracking-[-0.02em] text-tinta">
        {{ titulo }}
      </h1>
      <p
        v-if="descricao"
        class="mt-2 max-w-2xl text-[0.9375rem] leading-relaxed text-tinta-2"
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
