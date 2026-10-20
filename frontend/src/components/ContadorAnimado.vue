<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'

// Conta do valor anterior até o novo: quando o número muda (uma movimentação lançada,
// a página carregando), o olho vê que mudou e para onde. Curto, para não atrasar a
// leitura; e nada de animação para quem pediu menos movimento ao sistema.
const props = defineProps<{ valor: number }>()

const DURACAO_MS = 600
const exibido = ref(0)
let quadro = 0

function semMovimento() {
  return (
    typeof window.requestAnimationFrame !== 'function' ||
    typeof window.matchMedia !== 'function' ||
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

watch(
  () => props.valor,
  (alvo) => {
    if (quadro) cancelAnimationFrame(quadro)
    if (semMovimento()) {
      exibido.value = alvo
      return
    }
    const inicio = exibido.value
    const comeco = performance.now()
    const passo = (agora: number) => {
      const t = Math.min(1, (agora - comeco) / DURACAO_MS)
      const suave = 1 - (1 - t) ** 3 // desacelera ao chegar
      exibido.value = Math.round(inicio + (alvo - inicio) * suave)
      if (t < 1) quadro = requestAnimationFrame(passo)
    }
    quadro = requestAnimationFrame(passo)
  },
  { immediate: true },
)

onBeforeUnmount(() => quadro && cancelAnimationFrame(quadro))
</script>

<template>
  <!-- O leitor de tela ouve o valor final, não a contagem. -->
  <span
    aria-hidden="true"
    class="tabular-nums"
  >{{ exibido }}</span>
  <span class="sr-only">{{ valor }}</span>
</template>
