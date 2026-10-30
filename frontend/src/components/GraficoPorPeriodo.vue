<script setup lang="ts">
import { BarChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { type ECharts, type EChartsCoreOption, init, use } from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'
import { computed, onBeforeUnmount, onMounted, useTemplateRef, watch } from 'vue'

import { reais } from '@/formatos'
import { coresDoGrafico, temaAplicado } from '@/tema'
import type { PeriodoDoRelatorio } from '@/types/api'

// Só as peças que este gráfico usa: o ECharts inteiro passa de 1 MB.
use([BarChart, GridComponent, LegendComponent, TooltipComponent, SVGRenderer])

const props = defineProps<{ periodos: PeriodoDoRelatorio[] }>()

// Tokens do main.css: as opções do ECharts não leem CSS. Gasto no verde da marca, consumo
// no terra e perdas no vermelho dos alertas.
const CORES = { gasto: '#3f7a2c', consumo: '#a87f48', perdas: '#dc2626' }

/** O consumo do período em reais: a soma do que a API valorou, insumo por insumo. */
const consumoEmReais = (periodo: PeriodoDoRelatorio) =>
  periodo.consumo.reduce((soma, item) => soma + (item.valor ?? 0), 0)

const compacto = (valor: number) =>
  valor.toLocaleString('pt-BR', { notation: 'compact', maximumFractionDigits: 1 })

function opcoes(): EChartsCoreOption {
  const cores = coresDoGrafico.value
  return {
    textStyle: { fontFamily: "'Plus Jakarta Sans Variable', system-ui, sans-serif" },
    color: [CORES.gasto, CORES.consumo, CORES.perdas],
    legend: { top: 0, left: 0, icon: 'roundRect', textStyle: { color: cores.tinta } },
    grid: { top: 36, right: 8, bottom: 24, left: 8, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      valueFormatter: (valor: unknown) => reais(Number(valor)),
    },
    xAxis: {
      type: 'category',
      data: props.periodos.map((p) => p.rotulo),
      axisLabel: { color: cores.tinta },
      axisLine: { lineStyle: { color: cores.grade } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: cores.tinta, formatter: (valor: number) => `R$ ${compacto(valor)}` },
      splitLine: { lineStyle: { color: cores.grade } },
    },
    series: [
      { name: 'Gasto em compras', type: 'bar', data: props.periodos.map((p) => p.gasto), barMaxWidth: 18 },
      { name: 'Consumo', type: 'bar', data: props.periodos.map(consumoEmReais), barMaxWidth: 18 },
      { name: 'Perdas', type: 'bar', data: props.periodos.map((p) => p.perdas), barMaxWidth: 18 },
    ],
  }
}

// Para o leitor de tela, o mesmo que as barras dizem, em frase.
const descricao = computed(() => {
  const maior = [...props.periodos].sort((a, b) => b.gasto - a.gasto)[0]
  return maior && maior.gasto > 0
    ? `Gasto, consumo e perdas por período. O maior gasto foi em ${maior.rotulo}: ${reais(maior.gasto)}.`
    : 'Gasto, consumo e perdas por período: nada lançado no intervalo.'
})

const alvo = useTemplateRef<HTMLDivElement>('alvo')
let grafico: ECharts | undefined
let observador: ResizeObserver | undefined

onMounted(() => {
  grafico = init(alvo.value!, undefined, { renderer: 'svg' })
  grafico.setOption(opcoes())
  observador = new ResizeObserver(() => grafico?.resize())
  observador.observe(alvo.value!)
})
watch(
  () => [props.periodos, temaAplicado.value],
  () => grafico?.setOption(opcoes(), true),
)
onBeforeUnmount(() => {
  observador?.disconnect()
  grafico?.dispose()
})
</script>

<template>
  <div
    ref="alvo"
    role="img"
    :aria-label="descricao"
    class="h-72 w-full sm:h-80"
  />
</template>
