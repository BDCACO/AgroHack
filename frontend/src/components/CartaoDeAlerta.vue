<script setup lang="ts">
import type { Alerta, TipoAlerta } from '@/types/api'

import SeloDeGravidade from './SeloDeGravidade.vue'

// Sem `insumo`, o cartão está na página do próprio insumo e não repete o nome.
defineProps<{ alerta: Alerta; insumo?: { id: number; nome: string } }>()

const rotulo: Record<TipoAlerta, string> = {
  abaixo_do_minimo: 'Abaixo do mínimo',
  risco_de_falta: 'Risco de falta',
  vencido: 'Lote vencido',
  vencimento_proximo: 'Vencimento próximo',
  excesso: 'Excesso de estoque',
  baixa_movimentacao: 'Baixa movimentação',
  consumo_incomum: 'Consumo incomum',
}
</script>

<template>
  <li
    class="flex flex-col gap-2 rounded-lg border border-stone-200 bg-white p-4 sm:flex-row sm:items-start sm:gap-4"
    data-teste="alerta"
  >
    <!-- Largura fixa: alinha o texto dos cartões e não deixa o selo esticar no celular. -->
    <div class="shrink-0 sm:w-20">
      <SeloDeGravidade :gravidade="alerta.gravidade" />
    </div>
    <div>
      <p class="font-medium text-stone-800">
        {{ rotulo[alerta.tipo] }}<template v-if="insumo">
          ·
          <RouterLink
            :to="{ name: 'insumo', params: { id: insumo.id } }"
            class="hover:text-campo-700 hover:underline"
          >
            {{ insumo.nome }}
          </RouterLink>
        </template>
      </p>
      <p class="mt-0.5 text-sm text-stone-600">
        {{ alerta.justificativa }}
      </p>
    </div>
  </li>
</template>
