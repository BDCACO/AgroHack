<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, useId, useTemplateRef } from 'vue'

// larga: para formulários de vários campos, que no computador ficam em duas colunas.
defineProps<{ titulo: string; larga?: boolean }>()
const emit = defineEmits<{ fechar: [] }>()

const idDoTitulo = useId()
const janela = useTemplateRef<HTMLElement>('janela')
// Ao fechar, o foco volta para quem abriu (o botão "Remover" da linha): quem usa teclado
// ou leitor de tela continua de onde estava.
const focoAnterior = document.activeElement as HTMLElement | null

function aoTeclar(evento: KeyboardEvent) {
  if (evento.key === 'Escape') emit('fechar')
}

onMounted(() => {
  document.addEventListener('keydown', aoTeclar)
  nextTick(() => janela.value?.querySelector<HTMLElement>('[autofocus], button')?.focus())
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', aoTeclar)
  focoAnterior?.focus()
})
</script>

<template>
  <Teleport to="body">
    <!-- No celular, a janela sobe do pé da tela, perto do dedo; no computador, fica no meio. -->
    <div class="fixed inset-0 z-50 flex items-end justify-center bg-stone-900/40 sm:items-center sm:p-4">
      <div
        class="absolute inset-0"
        aria-hidden="true"
        @click="emit('fechar')"
      />
      <section
        ref="janela"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="idDoTitulo"
        class="cartao relative max-h-[90vh] w-full animate-surgir overflow-y-auto rounded-b-none p-5 shadow-xl sm:rounded-b-xl"
        :class="larga ? 'sm:max-w-2xl' : 'sm:max-w-md'"
      >
        <h2
          :id="idDoTitulo"
          class="text-lg font-semibold text-stone-900"
        >
          {{ titulo }}
        </h2>
        <div class="mt-3">
          <slot />
        </div>
      </section>
    </div>
  </Teleport>
</template>
