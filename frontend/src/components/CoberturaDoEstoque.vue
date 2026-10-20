<script setup lang="ts">
import { computed } from 'vue'

import type { Insumo } from '@/types/api'

// Quanto tempo cada insumo dura no ritmo atual, do mais apertado ao mais folgado. A conta
// (cobertura) e a situação (risco de falta, reposição, excesso) vêm da API; aqui só se
// desenha. A cor nunca anda sozinha: cada linha diz a situação em texto.
const props = defineProps<{ insumos: Insumo[] }>()

// A régua vai até 90 dias: além disso é folga, e um estoque para anos (excesso) não
// pode achatar todas as outras barras.
const ESCALA_DIAS = 90

const aparencia = {
  falta: { barra: 'bg-red-500', texto: 'text-red-700' },
  pedir: { barra: 'bg-amber-400', texto: 'text-amber-800' },
  folga: { barra: 'bg-campo-500', texto: 'text-stone-500' },
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
      // Cor só para o que pede ação agora; uma reposição para daqui a meses é texto,
      // não alarme — senão quase toda barra acende e a cor perde o sentido.
      const [situacao, texto] = tipos.includes('risco_de_falta')
        ? (['falta', 'acaba antes da entrega'] as const)
        : reposicao?.pedir_hoje
          ? (['pedir', 'pedir hoje'] as const)
          : reposicao
            ? (['folga', `pedir até ${dataBr(reposicao.pedir_em)}`] as const)
            : (['folga', tipos.includes('excesso') ? 'estoque de sobra' : 'em dia'] as const)
      return { insumo, dias, situacao, texto }
    })
    .sort((a, b) => a.dias - b.dias),
)

// Sem consumo recente (ou histórico curto), não há ritmo para projetar.
const semRitmo = computed(() =>
  props.insumos.filter((insumo) => insumo.analise.cobertura_dias === null),
)
</script>

<template>
  <section
    aria-labelledby="titulo-cobertura"
    class="cartao p-5"
  >
    <h2
      id="titulo-cobertura"
      class="text-base font-semibold text-stone-900"
    >
      Quanto tempo o estoque dura
    </h2>
    <p class="mt-0.5 text-sm text-stone-500">
      No ritmo de consumo atual, do mais apertado ao mais folgado.
    </p>

    <ul class="mt-5 space-y-4">
      <li
        v-for="(linha, indice) in linhas"
        :key="linha.insumo.id"
        class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1.5 sm:grid-cols-[minmax(0,12rem)_minmax(0,1fr)_10rem]"
        data-teste="cobertura"
      >
        <RouterLink
          :to="{ name: 'insumo', params: { id: linha.insumo.id } }"
          class="truncate text-sm font-medium text-stone-800 hover:text-campo-700 hover:underline"
        >
          {{ linha.insumo.nome }}
        </RouterLink>
        <div
          class="relative h-2.5 rounded-full bg-stone-100 max-sm:order-last max-sm:col-span-2"
          aria-hidden="true"
        >
          <!-- Cresce da esquerda, uma barra depois da outra: a ordem de leitura é a de
               urgência. -->
          <div
            class="absolute inset-y-0 left-0 origin-left animate-crescer rounded-full"
            :class="aparencia[linha.situacao].barra"
            :style="{ width: porcento(linha.dias), animationDelay: `${Math.min(indice, 8) * 60}ms` }"
          />
          <!-- A marca do prazo de entrega: barra que não passa dela acaba antes de o
               pedido chegar. -->
          <div
            v-if="linha.insumo.prazo_reposicao_dias !== null"
            class="absolute -top-1 -bottom-1 w-0.5 rounded-full bg-stone-700"
            :style="{ left: porcento(linha.insumo.prazo_reposicao_dias) }"
            :title="`Entrega em ${linha.insumo.prazo_reposicao_dias} dias`"
          />
        </div>
        <p class="text-right text-sm leading-tight sm:text-left">
          <span class="font-semibold text-stone-900 tabular-nums">
            {{ linha.dias.toLocaleString('pt-BR') }} {{ linha.dias === 1 ? 'dia' : 'dias' }}
          </span>
          <span
            class="block text-xs font-medium"
            :class="aparencia[linha.situacao].texto"
          >{{ linha.texto }}</span>
        </p>
      </li>
    </ul>

    <div
      v-if="semRitmo.length"
      class="mt-5 flex flex-wrap items-center gap-2 border-t border-stone-100 pt-4 text-sm text-stone-500"
    >
      Sem consumo recente para estimar:
      <RouterLink
        v-for="insumo in semRitmo"
        :key="insumo.id"
        :to="{ name: 'insumo', params: { id: insumo.id } }"
        class="rounded-full bg-stone-100 px-2.5 py-0.5 text-xs font-medium text-stone-700 transition-colors hover:bg-campo-100 hover:text-campo-800"
      >
        {{ insumo.nome }}
      </RouterLink>
    </div>

    <p class="mt-4 flex items-center gap-2 text-xs text-stone-500">
      <span
        class="inline-block h-3 w-0.5 rounded-full bg-stone-700"
        aria-hidden="true"
      />
      prazo de entrega do fornecedor · régua até 90 dias
    </p>
  </section>
</template>
