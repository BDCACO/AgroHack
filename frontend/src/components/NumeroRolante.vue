<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

// Cada dígito é uma coluna de 0 a 9 que desliza até o valor, como um contador mecânico.
// Só `transform`, então o navegador anima sem refazer o layout. Com "reduzir movimento",
// a regra global de main.css zera a transição e o número aparece direto.
const props = defineProps<{ valor: number }>()

// Começa em zero e, no quadro seguinte ao primeiro desenho, vai para o valor: é o que faz
// a primeira rolagem acontecer.
const pronto = ref(false)
onMounted(() => {
  const proximoQuadro = window.requestAnimationFrame ?? ((f: () => void) => setTimeout(f, 16))
  proximoQuadro(() => proximoQuadro(() => (pronto.value = true)))
})

// Da direita para a esquerda: a casa das unidades mantém a mesma coluna quando o número
// ganha uma casa, e a rolagem continua de onde estava.
const casas = computed(() =>
  props.valor
    .toLocaleString('pt-BR')
    .split('')
    .map((caractere, indice, todos) => ({
      caractere,
      chave: todos.length - indice,
      digito: caractere >= '0' && caractere <= '9' ? Number(caractere) : null,
    })),
)
</script>

<template>
  <span
    class="inline-flex tabular-nums"
    aria-hidden="true"
  >
    <span
      v-for="casa in casas"
      :key="casa.chave"
      class="inline-block h-[1em] overflow-hidden leading-none"
    >
      <span
        v-if="casa.digito !== null"
        class="block transition-transform duration-600 ease-chegar"
        :style="{
          transform: `translateY(-${pronto ? casa.digito * 10 : 0}%)`,
          transitionDelay: `${(casa.chave - 1) * 40}ms`,
        }"
      >
        <span
          v-for="n in 10"
          :key="n"
          class="block h-[1em]"
        >{{ n - 1 }}</span>
      </span>
      <span v-else>{{ casa.caractere }}</span>
    </span>
  </span>
  <span class="sr-only">{{ valor }}</span>
</template>
