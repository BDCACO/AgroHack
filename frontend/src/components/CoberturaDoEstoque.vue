<script setup lang="ts">
import { computed } from 'vue'

import type { Insumo } from '@/types/api'

// Dias de estoque de cada insumo no consumo atual, do menor para o maior. A conta e a
// situação vêm da API (cobertura, risco de falta, reposição); aqui só se desenha. Barras
// em tinta; cor só no que pede ação, e sempre com o texto ao lado.
const props = defineProps<{ insumos: Insumo[] }>()

// Escala até 90 dias: um estoque para anos (excesso) não pode achatar as outras barras.
const ESCALA_DIAS = 90

const aparencia = {
  falta: { barra: 'bg-urgente', texto: 'text-urgente' },
  pedir: { barra: 'bg-atencao-forte', texto: 'text-atencao' },
  folga: { barra: 'bg-tinta-2/70', texto: 'text-tinta-3' },
} as const

const dataBr = (data: string) => data.split('-').reverse().slice(0, 2).join('/')
const porcento = (dias: number) => `${(Math.min(dias, ESCALA_DIAS) / ESCALA_DIAS) * 100}%`

const linhas = computed(() =>
  props.insumos
    .filter((insumo) => insumo.analise.cobertura_dias !== null)
    .map((insumo) => {
      const { alertas, reposicao, cobertura_dias } = insumo.analise
      const tipos = alertas.map((alerta) => alerta.tipo)
      const dias = Math.round(cobertura_dias!)
      const [situacao, texto] = tipos.includes('risco_de_falta')
        ? (['falta', 'acaba antes da entrega'] as const)
        : reposicao?.pedir_hoje
          ? (['pedir', 'pedir hoje'] as const)
          : reposicao
            ? (['folga', `pedir até ${dataBr(reposicao.pedir_em)}`] as const)
            : (['folga', tipos.includes('excesso') ? 'excesso' : 'em dia'] as const)
      return { insumo, dias, situacao, texto }
    })
    .sort((a, b) => a.dias - b.dias),
)

// Sem consumo recente (ou com histórico curto) não há ritmo para projetar.
const semRitmo = computed(() =>
  props.insumos.filter((insumo) => insumo.analise.cobertura_dias === null),
)
</script>

<template>
  <section aria-labelledby="titulo-cobertura">
    <h2
      id="titulo-cobertura"
      class="titulo-secao"
    >
      Dias de estoque
    </h2>
    <p class="mt-1 text-sm text-tinta-3">
      No consumo médio dos últimos 90 dias.
    </p>

    <ul class="mt-5 divide-y divide-linha border-y border-linha">
      <li
        v-for="(linha, indice) in linhas"
        :key="linha.insumo.id"
        class="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-4 gap-y-2 py-3"
        data-teste="cobertura"
      >
        <RouterLink
          :to="{ name: 'insumo', params: { id: linha.insumo.id } }"
          class="truncate text-sm text-tinta transition-colors duration-150 hover:text-campo-700"
        >
          {{ linha.insumo.nome }}
        </RouterLink>
        <p class="text-right leading-none whitespace-nowrap">
          <span class="font-serif text-lg text-tinta tabular-nums">{{ linha.dias.toLocaleString('pt-BR') }}</span>
          <span class="text-xs text-tinta-3">{{ ' ' + (linha.dias === 1 ? 'dia' : 'dias') }}</span>
        </p>
        <div
          class="relative col-span-2 h-1 rounded-full bg-linha"
          aria-hidden="true"
        >
          <!-- Cresce da esquerda, uma depois da outra, na ordem da lista. -->
          <div
            class="absolute inset-y-0 left-0 origin-left animate-crescer rounded-full"
            :class="aparencia[linha.situacao].barra"
            :style="{ width: porcento(linha.dias), animationDelay: `${120 + indice * 40}ms` }"
          />
          <!-- Prazo de entrega: barra que não chega até aqui acaba antes do pedido. -->
          <div
            v-if="linha.insumo.prazo_reposicao_dias !== null"
            class="absolute -top-1 -bottom-1 w-px bg-tinta"
            :style="{ left: porcento(linha.insumo.prazo_reposicao_dias) }"
            :title="`Entrega em ${linha.insumo.prazo_reposicao_dias} dias`"
          />
        </div>
        <p
          class="col-span-2 -mt-1 text-xs"
          :class="aparencia[linha.situacao].texto"
        >
          {{ linha.texto }}
        </p>
      </li>
    </ul>

    <p
      v-if="semRitmo.length"
      class="mt-4 text-xs leading-relaxed text-tinta-3"
    >
      Sem consumo recente para estimar:
      <!-- A vírgula vem do ::after, que não aparece no último. -->
      <span
        v-for="insumo in semRitmo"
        :key="insumo.id"
        class="after:content-[',_'] last:after:content-none"
      >
        <RouterLink
          :to="{ name: 'insumo', params: { id: insumo.id } }"
          class="text-tinta-2 underline decoration-linha-forte underline-offset-2 hover:decoration-tinta-3"
        >
          {{ insumo.nome }}
        </RouterLink>
      </span>
    </p>
    <p class="mt-3 flex items-center gap-2 text-xs text-tinta-3">
      <span
        class="inline-block h-3 w-px bg-tinta"
        aria-hidden="true"
      />
      prazo de entrega · escala até 90 dias
    </p>
  </section>
</template>
