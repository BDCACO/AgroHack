<script setup lang="ts">
import { computed } from 'vue'

import type { Gravidade } from '@/types/api'

// null = insumo sem alertas.
const props = defineProps<{ gravidade: Gravidade | null }>()

const aparencia = computed(
  () =>
    ({
      alta: { texto: 'Urgente', classes: 'bg-red-50 text-red-800 ring-red-600/20', ponto: 'bg-red-600' },
      media: { texto: 'Atenção', classes: 'bg-amber-50 text-amber-800 ring-amber-600/25', ponto: 'bg-amber-500' },
      baixa: { texto: 'Observar', classes: 'bg-sky-50 text-sky-800 ring-sky-600/20', ponto: 'bg-sky-500' },
      nenhuma: { texto: 'Sem alertas', classes: 'bg-campo-50 text-campo-800 ring-campo-600/20', ponto: 'bg-campo-500' },
    })[props.gravidade ?? 'nenhuma'],
)
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-semibold whitespace-nowrap ring-1 ring-inset"
    :class="aparencia.classes"
  >
    <!-- Só o urgente pulsa: é o único que não pode esperar. -->
    <span
      class="h-1.5 w-1.5 rounded-full"
      :class="[aparencia.ponto, gravidade === 'alta' ? 'animate-pulsar' : '']"
      aria-hidden="true"
    />
    {{ aparencia.texto }}
  </span>
</template>
