<script setup lang="ts">
import { computed } from 'vue'

import type { Gravidade } from '@/types/api'

// null = insumo sem alertas.
const props = defineProps<{ gravidade: Gravidade | null }>()

const aparencia = computed(
  () =>
    ({
      alta: { texto: 'Urgente', tinta: 'text-urgente', marca: 'bg-urgente' },
      media: { texto: 'Atenção', tinta: 'text-atencao', marca: 'bg-atencao-forte' },
      baixa: { texto: 'Observar', tinta: 'text-observar', marca: 'bg-observar' },
      nenhuma: { texto: 'Sem alertas', tinta: 'text-tinta-3', marca: 'bg-linha-forte' },
    })[props.gravidade ?? 'nenhuma'],
)
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 text-xs font-semibold whitespace-nowrap"
    :class="aparencia.tinta"
  >
    <span
      class="size-[7px] rounded-[2px]"
      :class="aparencia.marca"
      aria-hidden="true"
    />
    {{ aparencia.texto }}
  </span>
</template>
