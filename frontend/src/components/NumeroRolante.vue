<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

// Cada dígito é uma coluna de 0 a 9 que rola até o valor, como um contador mecânico.
// Quando o número muda, só os dígitos que mudaram se mexem. Só `transform`: o navegador
// anima sem refazer o layout. Com "reduzir movimento", a regra global de main.css zera a
// transição e o número aparece direto.
const props = defineProps<{ valor: number }>()

// Começa em zero e, dois quadros depois do primeiro desenho, vai para o valor: é o que faz
// a primeira rolagem acontecer.
const pronto = ref(false)
onMounted(() => {
  const proximoQuadro = window.requestAnimationFrame ?? ((f: () => void) => setTimeout(f, 16))
  proximoQuadro(() => proximoQuadro(() => (pronto.value = true)))
})

// Chave contada da direita: a casa das unidades continua a mesma quando o número ganha uma
// casa, e a rolagem segue de onde estava.
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
  <!-- O dígito invisível dá a largura, a altura e a linha de base: parado, o número fica
       exatamente onde um texto comum ficaria. A coluna corre por cima, recortada nele. -->
  <span
    class="tabular-nums"
    aria-hidden="true"
  >
    <template
      v-for="casa in casas"
      :key="casa.chave"
    >
      <span v-if="casa.digito === null">{{ casa.caractere }}</span>
      <span
        v-else
        class="relative inline-block [clip-path:inset(0)]"
      >
        <span class="invisible">{{ casa.caractere }}</span>
        <span
          class="absolute inset-x-0 top-0 transition-transform duration-600 ease-chegada"
          :style="{
            transform: `translateY(-${pronto ? casa.digito * 10 : 0}%)`,
            transitionDelay: `${(casa.chave - 1) * 40}ms`,
          }"
        >
          <span
            v-for="n in 10"
            :key="n"
            class="block"
          >{{ n - 1 }}</span>
        </span>
      </span>
    </template>
  </span>
  <span class="sr-only">{{ valor }}</span>
</template>
