<script setup lang="ts">
import IconeSvg, { type NomeIcone } from './IconeSvg.vue'

defineProps<{
  icone: NomeIcone
  titulo: string
  texto: string
}>()
</script>

<template>
  <div class="cartao flex animate-surgir flex-col items-center px-6 py-14 text-center">
    <!-- Anéis em volta do ícone: um broto de lavoura visto de cima. -->
    <div
      class="relative flex h-24 w-24 items-center justify-center"
      aria-hidden="true"
    >
      <span class="absolute inset-0 rounded-full bg-campo-50" />
      <span class="absolute inset-3 rounded-full bg-campo-100" />
      <span class="relative rounded-full bg-superficie p-3 text-campo-600 shadow-sm">
        <IconeSvg
          :nome="icone"
          class="h-8 w-8"
        />
      </span>
    </div>
    <h2 class="mt-5 text-lg font-semibold text-stone-900">
      {{ titulo }}
    </h2>
    <p class="mt-1.5 max-w-md text-sm leading-relaxed text-stone-600">
      {{ texto }}
    </p>
    <div
      v-if="$slots.default"
      class="mt-6 flex flex-wrap items-center justify-center gap-2"
    >
      <slot />
    </div>
  </div>
</template>
