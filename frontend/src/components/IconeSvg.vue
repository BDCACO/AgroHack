<script setup lang="ts">
// Ícones a traço, desenhados aqui no mesmo estilo da marca (traço de 1,75, pontas
// arredondadas, grade de 24). Duas dezenas não justificam uma biblioteca: cada um é uma
// linha, e o bundle não carrega os que não se usam.
const caminhos = {
  painel: 'M4 4h6v7H4z M14 4h6v4h-6z M14 12h6v8h-6z M4 15h6v5H4z',
  insumos: 'M3.5 7.5 12 3.5l8.5 4v9L12 20.5l-8.5-4z M3.5 7.5 12 11.5l8.5-4 M12 11.5v9',
  movimentacoes: 'M4 8h15 M15.5 4.5 19 8l-3.5 3.5 M20 16H5 M8.5 12.5 5 16l3.5 3.5',
  importar: 'M12 15V4 M7.5 8.5 12 4l4.5 4.5 M4 14.5v3A2.5 2.5 0 0 0 6.5 20h11a2.5 2.5 0 0 0 2.5-2.5v-3',
  sistema: 'M3 12h4l2.5-6.5 5 13L17 12h4',
  alerta: 'M12 4 21 19.5H3z M12 10v4 M12 17h.01',
  urgente: 'M20.5 12a8.5 8.5 0 1 1-17 0 8.5 8.5 0 0 1 17 0z M12 7.5V13 M12 16.5h.01',
  relogio: 'M20.5 12a8.5 8.5 0 1 1-17 0 8.5 8.5 0 0 1 17 0z M12 7.5V12l3 2',
  olho: 'M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z M14.75 12a2.75 2.75 0 1 1-5.5 0 2.75 2.75 0 0 1 5.5 0z',
  seta: 'm9.5 6 6 6-6 6',
  atualizar: 'M19.5 12a7.5 7.5 0 1 1-2.2-5.3 M19.5 4.5v4.5H15',
  enviar: 'M20.5 3.5 10 14 M20.5 3.5 14 20.5l-4-6.5-6.5-4z',
  copiar: 'M8.5 8.5h11v11h-11z M15.5 8.5v-4h-11v11h4',
  baixar: 'M12 4v11 M7.5 10.5 12 15l4.5-4.5 M4 15.5v2A2.5 2.5 0 0 0 6.5 20h11a2.5 2.5 0 0 0 2.5-2.5v-2',
  confirmado: 'M20.5 12a8.5 8.5 0 1 1-17 0 8.5 8.5 0 0 1 17 0z M8.5 12.5l2.5 2.5 4.5-5.5',
  folha: 'M5 19.5C5 11 10 5.5 19.5 4.5 19 14 13.5 19.5 5 19.5z M5 19.5c3-3.5 6-6 9.5-8',
  calendario: 'M4.5 6h15v14h-15z M4.5 10h15 M8.5 3.5V7 M15.5 3.5V7',
  menu: 'M4 7h16 M4 12h16 M4 17h16',
  fechar: 'M6.5 6.5l11 11 M17.5 6.5l-11 11',
} as const

export type NomeIcone = keyof typeof caminhos

defineProps<{ nome: NomeIcone }>()
</script>

<template>
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.75"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path :d="caminhos[nome]" />
  </svg>
</template>
