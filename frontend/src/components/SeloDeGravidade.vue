<script setup lang="ts">
import { computed } from 'vue'

import type { Gravidade } from '@/types/api'

// null = insumo sem alertas.
const props = defineProps<{ gravidade: Gravidade | null }>()

const aparencia = computed(
  () =>
    ({
      alta: { texto: 'Urgente', classes: 'bg-red-100 text-red-800' },
      media: { texto: 'Atenção', classes: 'bg-amber-100 text-amber-800' },
      baixa: { texto: 'Observar', classes: 'bg-sky-100 text-sky-800' },
      nenhuma: { texto: 'Sem alertas', classes: 'bg-campo-100 text-campo-700' },
    })[props.gravidade ?? 'nenhuma'],
)
</script>

<template>
  <span
    class="inline-flex rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap"
    :class="aparencia.classes"
  >
    {{ aparencia.texto }}
  </span>
</template>
