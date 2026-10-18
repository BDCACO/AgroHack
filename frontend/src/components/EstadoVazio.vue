<script setup lang="ts">
import IconeSvg, { type NomeIcone } from './IconeSvg.vue'

defineProps<{
  icone: NomeIcone
  titulo: string
  texto: string
}>()
</script>

<template>
  <div class="flex flex-col items-center px-4 py-14 text-center">
    <div class="rounded-full bg-campo-50 p-4 text-campo-600">
      <IconeSvg
        :nome="icone"
        class="h-8 w-8"
      />
    </div>
    <h2 class="mt-4 text-lg font-semibold text-stone-800">
      {{ titulo }}
    </h2>
    <p class="mt-1 max-w-md text-sm text-stone-600">
      {{ texto }}
    </p>
    <div
      v-if="$slots.default"
      class="mt-5"
    >
      <slot />
    </div>
  </div>
</template>
