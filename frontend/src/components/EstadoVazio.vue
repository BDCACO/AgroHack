<script setup lang="ts">
import IconeSvg, { type NomeIcone } from './IconeSvg.vue'

defineProps<{
  icone: NomeIcone
  titulo: string
  texto: string
}>()
</script>

<template>
  <div class="flex animate-surgir flex-col items-start border-y border-linha py-12 sm:py-16">
    <IconeSvg
      :nome="icone"
      class="size-6 text-campo-700"
    />
    <h2 class="mt-4 font-serif text-2xl font-medium tracking-[-0.01em] text-tinta">
      {{ titulo }}
    </h2>
    <p class="mt-2 max-w-lg text-[0.9375rem] leading-relaxed text-tinta-2">
      {{ texto }}
    </p>
    <div
      v-if="$slots.default"
      class="mt-6 flex flex-wrap items-center gap-2"
    >
      <slot />
    </div>
  </div>
</template>
