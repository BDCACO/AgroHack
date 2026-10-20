<script setup lang="ts">
import { computed } from 'vue'

import type { EstadoServico } from '@/stores/statusSistema'

const props = defineProps<{
  rotulo: string
  estado: EstadoServico
}>()

const aparencia = computed(
  () =>
    ({
      ok: { texto: 'Operando', ponto: 'bg-campo-600' },
      erro: { texto: 'Indisponível', ponto: 'bg-urgente' },
      desconhecido: { texto: 'Não verificado', ponto: 'bg-linha-forte' },
    })[props.estado],
)
</script>

<template>
  <div class="flex items-center justify-between gap-4 py-3">
    <span class="font-medium">{{ rotulo }}</span>
    <span
      class="flex items-center gap-2 text-sm text-tinta-2"
      :data-estado="estado"
    >
      <span
        class="h-2.5 w-2.5 rounded-full"
        :class="aparencia.ponto"
        aria-hidden="true"
      />
      {{ aparencia.texto }}
    </span>
  </div>
</template>
