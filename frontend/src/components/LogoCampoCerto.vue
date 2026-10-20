<script setup lang="ts">
// O selo da marca: um broto saindo da terra. Desenhado aqui, em SVG, para ficar nítido
// em qualquer tamanho e herdar a cor de onde estiver.
defineProps<{ comNome?: boolean }>()
</script>

<template>
  <span class="inline-flex items-center gap-2.5">
    <svg
      viewBox="0 0 32 32"
      class="h-8 w-8 shrink-0"
      aria-hidden="true"
    >
      <rect
        width="32"
        height="32"
        rx="9"
        class="fill-campo-500"
      />
      <!-- Terra -->
      <path
        d="M6 24.5c3.2-1.6 6.5-2.4 10-2.4s6.8.8 10 2.4"
        fill="none"
        stroke="white"
        stroke-width="2"
        stroke-linecap="round"
        opacity="0.55"
      />
      <!-- Caule -->
      <path
        d="M16 22V13.5"
        fill="none"
        stroke="white"
        stroke-width="2"
        stroke-linecap="round"
      />
      <!-- Folhas -->
      <path
        d="M16 15.5c0-4 2.6-6.6 7-6.8-.1 4.3-2.8 6.8-7 6.8Z"
        fill="white"
      />
      <path
        d="M16 17.5c0-3.4-2.2-5.6-6-5.8.1 3.7 2.4 5.8 6 5.8Z"
        fill="white"
        opacity="0.85"
      />
    </svg>
    <span
      v-if="comNome"
      class="text-lg font-bold tracking-tight"
    >Campo<span class="font-medium opacity-80">Certo</span></span>
  </span>
</template>
