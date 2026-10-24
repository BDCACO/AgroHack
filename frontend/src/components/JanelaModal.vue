<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'

defineProps<{ titulo: string }>()
const emit = defineEmits<{ fechar: [] }>()

function aoTeclar(evento: KeyboardEvent) {
  if (evento.key === 'Escape') emit('fechar')
}

onMounted(() => document.addEventListener('keydown', aoTeclar))
onBeforeUnmount(() => document.removeEventListener('keydown', aoTeclar))
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center sm:p-4">
      <div
        class="absolute inset-0"
        aria-hidden="true"
        @click="emit('fechar')"
      />
      <section
        role="dialog"
        aria-modal="true"
        :aria-label="titulo"
        class="relative max-h-[90vh] w-full overflow-y-auto rounded-t-xl bg-white p-5 shadow-xl sm:max-w-lg sm:rounded-xl"
      >
        <h2 class="text-lg font-semibold text-stone-900">
          {{ titulo }}
        </h2>
        <div class="mt-4">
          <slot />
        </div>
      </section>
    </div>
  </Teleport>
</template>
