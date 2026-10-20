<script setup lang="ts">
import { LineChart } from 'echarts/charts'
import { GridComponent, MarkLineComponent, TooltipComponent } from 'echarts/components'
import { type ECharts, type EChartsCoreOption, format, init, use } from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'
import { computed, onBeforeUnmount, onMounted, useTemplateRef, watch } from 'vue'

import type { InsumoDetalhe } from '@/types/api'

// Só as peças que este gráfico usa: o ECharts inteiro passa de 1 MB.
use([LineChart, GridComponent, MarkLineComponent, TooltipComponent, SVGRenderer])

const props = defineProps<{ insumo: InsumoDetalhe; hoje: string }>()

// Tokens do main.css (campo-600 e os cinzas stone): as opções do ECharts não leem CSS.
const COR = '#3f7a2c'
const TINTA = '#57534e'
const TINTA_SUAVE = '#78716c'
const GRADE = '#e7e5e4'
// Projetar além disso só esticaria o eixo: estoque para meses já é alerta de excesso.
const HORIZONTE_DIAS = 90

type Ponto = [string, number]

const quantidade = (valor: number, unidade: string) =>
  `${valor.toLocaleString('pt-BR', { maximumFractionDigits: 3 })} ${unidade}`
const dataBr = (data: string) => data.split('-').reverse().join('/')

function somarDias(data: string, dias: number): string {
  const dia = new Date(`${data}T12:00:00`)
  dia.setDate(dia.getDate() + dias)
  return dia.toLocaleDateString('sv-SE')
}

/** Até onde a linha tracejada vai: o dia em que zera no ritmo atual, ou o horizonte.
 * A cobertura vem da API, com o mesmo arredondamento do cartão "Dura cerca de" e do
 * alerta: a página não pode dizer 8 dias num lugar e 9 no outro. */
const projecao = computed(() => {
  const { estoque_atual: estoque, analise } = props.insumo
  const { consumo_diario: consumo, cobertura_dias: cobertura } = analise
  if (!consumo || cobertura === null || estoque <= 0) return null
  const dias = Math.round(cobertura)
  if (dias > HORIZONTE_DIAS) {
    return { dias: HORIZONTE_DIAS, zera: false, saldo: estoque - consumo * HORIZONTE_DIAS }
  }
  return { dias, zera: true, saldo: 0 }
})
const quandoZera = (dias: number) =>
  dias === 0 ? 'zera hoje' : `zera em ~${dias} ${dias === 1 ? 'dia' : 'dias'}`

const descricao = computed(() => {
  const { nome, unidade, estoque_atual } = props.insumo
  const fim = projecao.value?.zera ? `; no ritmo atual, ${quandoZera(projecao.value.dias)}` : ''
  return `Estoque de ${nome} ao longo do tempo: ${quantidade(estoque_atual, unidade)} hoje${fim}.`
})

function opcoes(): EChartsCoreOption {
  const { unidade, estoque_atual, estoque_minimo, historico } = props.insumo
  const real: Ponto[] = historico.map((ponto) => [ponto.data, ponto.saldo])
  // Sem movimentação recente, o saldo se mantém até hoje.
  const ultimo = real.at(-1)
  if (ultimo && ultimo[0] < props.hoje) real.push([props.hoje, estoque_atual])
  const p = projecao.value
  const projetada: Ponto[] = p
    ? [
        [props.hoje, estoque_atual],
        [somarDias(props.hoje, p.dias), p.saldo],
      ]
    : []

  const referencias: object[] = [{ xAxis: props.hoje, label: { formatter: 'hoje', position: 'end' } }]
  if (estoque_minimo) {
    referencias.push({
      yAxis: estoque_minimo,
      label: { formatter: `mínimo ${quantidade(estoque_minimo, unidade)}`, position: 'insideStartTop' },
    })
  }

  return {
    animationDuration: 300,
    grid: { left: 8, right: 24, top: 24, bottom: 8, containLabel: true },
    xAxis: {
      type: 'time',
      axisLine: { lineStyle: { color: GRADE } },
      axisTick: { show: false },
      axisLabel: { color: TINTA_SUAVE, formatter: '{dd}/{MM}', hideOverlap: true },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      // Saldo negativo (lançamento faltando) aparece, em vez de ser cortado no zero.
      min: (extremos: { min: number }) => Math.min(0, extremos.min),
      axisLabel: { color: TINTA_SUAVE, formatter: (valor: number) => valor.toLocaleString('pt-BR') },
      splitLine: { lineStyle: { color: GRADE } },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line', lineStyle: { color: TINTA_SUAVE, width: 1 } },
      formatter: (itens: unknown) => {
        const lista = itens as { seriesName: string; value: Ponto }[]
        const linhas = lista.map(
          (item) => `${item.seriesName}: ${quantidade(item.value[1], unidade)}`,
        )
        // Unidade é texto digitado pelo usuário, e o tooltip é HTML: escapar.
        return [dataBr(lista[0]!.value[0]), ...linhas].map(format.encodeHTML).join('<br>')
      },
    },
    series: [
      {
        name: 'Estoque',
        type: 'line',
        // O saldo vale do dia da movimentação até a próxima: degrau, não rampa.
        step: 'end',
        data: real,
        // Com um ponto só (insumo recém-cadastrado), sem o marcador não aparece nada.
        showSymbol: real.length === 1,
        color: COR,
        lineStyle: { width: 2 },
        areaStyle: { opacity: 0.1 },
        markLine: {
          symbol: 'none',
          silent: true,
          lineStyle: { color: TINTA_SUAVE, type: 'dashed', width: 1 },
          label: { color: TINTA },
          data: referencias,
        },
      },
      {
        name: 'Projeção',
        type: 'line',
        data: projetada,
        showSymbol: false,
        color: COR,
        lineStyle: { width: 2, type: 'dashed', opacity: 0.7 },
      },
    ],
  }
}

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
  () => [props.insumo, props.hoje],
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
    class="h-64 w-full sm:h-80"
  />
</template>
