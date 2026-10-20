<script setup lang="ts">
// Marca: um broto desenhado a traço, e o nome em serifa. Herda a cor de onde estiver.
defineProps<{ comNome?: boolean }>()
</script>

<template>
  <span class="inline-flex items-center gap-2">
    <svg
      viewBox="0 0 24 24"
      class="size-6 shrink-0 text-campo-700"
      fill="none"
      stroke="currentColor"
      stroke-width="1.6"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path d="M3.5 20.5h17" />
      <path d="M12 20.5v-9" />
      <path
        d="M12 13.5c0-4.2 2.7-7 7-7.2-.1 4.4-2.8 7.2-7 7.2Z"
        fill="currentColor"
        fill-opacity="0.18"
      />
      <path d="M12 15.5c0-3.4-2.2-5.7-5.8-5.9.1 3.6 2.3 5.9 5.8 5.9Z" />
    </svg>
    <span
      v-if="comNome"
      class="font-serif text-[1.15rem] font-semibold tracking-[-0.015em] text-tinta"
    >CampoCerto</span>
  </span>
</template>
