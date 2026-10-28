<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import CartaoDeAlerta from '@/components/CartaoDeAlerta.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
import IconeSvg from '@/components/IconeSvg.vue'
import { reais } from '@/formatos'
import { buscarTalhao } from '@/services/talhoes'
import { mensagemDeErro } from '@/stores/estoque'
import type { TalhaoDetalhe } from '@/types/api'

const props = defineProps<{ id: number }>()

// O período recorta uma safra no custo, no consumo e nas aplicações. A carência continua
// olhando todas as aplicações: um defensivo de antes do recorte ainda proíbe colher.
const periodo = reactive({ desde: '', ate: '' })
const talhao = ref<TalhaoDetalhe | null>(null)
const erro = ref<string | null>(null)

async function carregar() {
  erro.value = null
  try {
    talhao.value = await buscarTalhao(props.id, periodo)
  } catch (falha) {
    erro.value = mensagemDeErro(falha)
  }
}
watch([() => props.id, () => periodo.desde, () => periodo.ate], carregar, { immediate: true })

const numero = (valor: number, casas = 3) =>
  valor.toLocaleString('pt-BR', { maximumFractionDigits: casas })
const dataBr = (data: string) => data.split('-').reverse().join('/')

const descricao = computed(() => {
  if (!talhao.value) return undefined
  const { cultura, area_ha: area } = talhao.value
  return [cultura, `${numero(area, 2)} hectares`].filter(Boolean).join(' · ')
})
</script>

<template>
  <RouterLink
    :to="{ name: 'talhoes' }"
    class="group mb-4 inline-flex items-center gap-1 text-sm font-semibold text-campo-700 hover:text-campo-900"
  >
    <IconeSvg
      nome="seta"
      class="h-4 w-4 rotate-180 transition-transform duration-200 ease-chegada group-hover:-translate-x-1"
    />
    Talhões
  </RouterLink>

  <p
    v-if="erro"
    role="alert"
    class="cartao border-red-200 bg-red-50 p-4 text-sm text-red-800"
  >
    {{ erro }}
  </p>

  <template v-else-if="talhao">
    <CabecalhoDePagina
      :titulo="talhao.nome"
      :descricao="descricao"
    />

    <ul
      v-if="talhao.alertas.length"
      class="mb-6 space-y-2"
    >
      <CartaoDeAlerta
        v-for="alerta in talhao.alertas"
        :key="alerta.justificativa"
        :alerta="alerta"
      />
    </ul>
    <p
      v-else
      class="cartao mb-6 flex items-center gap-3 p-4 text-sm text-stone-600"
    >
      <IconeSvg
        nome="confirmado"
        class="h-6 w-6 shrink-0 text-campo-500"
      />
      {{ talhao.colheita_liberada_em === null
        ? 'Nada com carência foi aplicado aqui.'
        : `Colheita liberada desde ${dataBr(talhao.colheita_liberada_em)}.` }}
    </p>

    <fieldset class="flex flex-wrap items-end gap-3">
      <legend class="mb-1 text-sm font-medium text-stone-700">
        Período <span class="font-normal text-stone-500">(a safra; vazio = desde o início)</span>
      </legend>
      <label class="flutuante">
        <input
          v-model="periodo.desde"
          type="date"
          class="campo"
          data-teste="desde"
        >
        <span class="rotulo">De</span>
      </label>
      <label class="flutuante">
        <input
          v-model="periodo.ate"
          type="date"
          class="campo"
          data-teste="ate"
        >
        <span class="rotulo">Até</span>
      </label>
    </fieldset>

    <dl class="mt-4 grid grid-cols-2 gap-3">
      <div class="cartao p-4">
        <dt class="text-sm text-stone-500">
          Custo aplicado
        </dt>
        <dd class="mt-1 text-xl font-bold text-stone-900 tabular-nums">
          {{ talhao.custo_total === null ? '—' : reais(talhao.custo_total) }}
        </dd>
      </div>
      <div class="cartao p-4">
        <dt class="text-sm text-stone-500">
          Por hectare
        </dt>
        <dd class="mt-1 text-xl font-bold text-stone-900 tabular-nums">
          {{ talhao.custo_por_ha === null ? '—' : reais(talhao.custo_por_ha) }}
        </dd>
      </div>
    </dl>

    <EstadoVazio
      v-if="!talhao.aplicacoes.length"
      icone="movimentacoes"
      titulo="Nenhuma aplicação no período"
      texto="Ao lançar uma retirada em Movimentações, escolha este talhão em &quot;Aplicado no talhão&quot;."
    />

    <template v-else>
      <section
        aria-labelledby="titulo-consumo"
        class="mt-6"
      >
        <h2
          id="titulo-consumo"
          class="text-base font-semibold text-stone-900"
        >
          O que foi aplicado
        </h2>
        <ul class="cartao mt-2 divide-y divide-stone-100">
          <li
            v-for="item in talhao.consumo"
            :key="item.insumo_id"
            class="flex items-baseline justify-between gap-3 px-4 py-3 text-sm"
            data-teste="consumo"
          >
            <RouterLink
              :to="{ name: 'insumo', params: { id: item.insumo_id } }"
              class="font-medium text-stone-800 hover:text-campo-700 hover:underline"
            >
              {{ item.insumo }}
            </RouterLink>
            <span class="text-right text-stone-600 tabular-nums">
              {{ numero(item.quantidade) }} {{ item.unidade }}
              <span class="block font-semibold text-stone-900">
                {{ item.custo === null ? 'sem preço' : reais(item.custo) }}
              </span>
            </span>
          </li>
        </ul>
      </section>

      <section
        aria-labelledby="titulo-aplicacoes"
        class="mt-6"
      >
        <h2
          id="titulo-aplicacoes"
          class="text-base font-semibold text-stone-900"
        >
          Aplicações
          <span class="ml-1 text-sm font-normal text-stone-500 tabular-nums">{{ talhao.aplicacoes.length }}</span>
        </h2>
        <ul class="cartao mt-2 divide-y divide-stone-100">
          <li
            v-for="aplicacao in talhao.aplicacoes"
            :key="aplicacao.id"
            class="flex items-baseline justify-between gap-3 px-4 py-2.5 text-sm"
            data-teste="aplicacao"
          >
            <span class="text-stone-600 tabular-nums">{{ dataBr(aplicacao.data) }}</span>
            <span class="min-w-0 flex-1 truncate text-stone-800">
              {{ talhao.consumo.find((c) => c.insumo_id === aplicacao.insumo_id)?.insumo }}
              <span
                v-if="aplicacao.lancado_por"
                class="text-xs text-stone-500"
              >· por {{ aplicacao.lancado_por }}</span>
            </span>
            <span class="font-semibold text-stone-800 tabular-nums">
              {{ numero(aplicacao.quantidade) }}
              {{ talhao.consumo.find((c) => c.insumo_id === aplicacao.insumo_id)?.unidade }}
            </span>
          </li>
        </ul>
      </section>
    </template>

    <section
      v-if="talhao.limitacoes.length"
      aria-labelledby="titulo-limitacoes"
      class="mt-6"
    >
      <h2
        id="titulo-limitacoes"
        class="text-base font-semibold text-stone-900"
      >
        Limitações
      </h2>
      <ul class="mt-2 list-disc space-y-1 pl-5 text-sm text-stone-600">
        <li
          v-for="limitacao in talhao.limitacoes"
          :key="limitacao"
        >
          {{ limitacao }}
        </li>
      </ul>
    </section>
  </template>
</template>
