<script setup lang="ts">
const modelo = defineModel<number[]>({ required: true })

const MESES = [
  { numero: 1, nome: 'Jan' },
  { numero: 2, nome: 'Fev' },
  { numero: 3, nome: 'Mar' },
  { numero: 4, nome: 'Abr' },
  { numero: 5, nome: 'Mai' },
  { numero: 6, nome: 'Jun' },
  { numero: 7, nome: 'Jul' },
  { numero: 8, nome: 'Ago' },
  { numero: 9, nome: 'Set' },
  { numero: 10, nome: 'Out' },
  { numero: 11, nome: 'Nov' },
  { numero: 12, nome: 'Dez' },
]

function alternar(mes: number) {
  modelo.value = modelo.value.includes(mes)
    ? modelo.value.filter((m) => m !== mes)
    : [...modelo.value, mes].sort((a, b) => a - b)
}
</script>

<template>
  <div
    class="grid grid-cols-4 gap-2 sm:grid-cols-6"
    role="group"
    aria-label="Meses de safra"
  >
    <button
      v-for="mes in MESES"
      :key="mes.numero"
      type="button"
      class="botao-secundario justify-center"
      :class="modelo.includes(mes.numero) ? '!bg-campo-600 !text-white hover:!bg-campo-700' : ''"
      :aria-pressed="modelo.includes(mes.numero)"
      @click="alternar(mes.numero)"
    >
      {{ mes.nome }}
    </button>
  </div>
</template>
