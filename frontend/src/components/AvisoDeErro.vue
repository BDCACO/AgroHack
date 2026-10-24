<script setup lang="ts">
defineProps<{ mensagem: string }>()
</script>

<template>
  <p
    role="alert"
    class="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"
  >
    {{ mensagem }}
  </p>
</template>
