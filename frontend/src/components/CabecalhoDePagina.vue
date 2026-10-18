<script setup lang="ts">
defineProps<{
  titulo: string
  descricao?: string
}>()
</script>

<template>
  <header class="flex flex-col gap-3 border-b border-stone-200 pb-5 sm:flex-row sm:items-end sm:justify-between">
    <div>
      <h1 class="text-2xl font-semibold tracking-tight text-campo-900">
        {{ titulo }}
      </h1>
      <p
        v-if="descricao"
        class="mt-1 max-w-2xl text-sm text-stone-600"
      >
        {{ descricao }}
      </p>
    </div>
    <div
      v-if="$slots.acoes"
      class="flex gap-2"
    >
      <slot name="acoes" />
    </div>
  </header>
</template>
