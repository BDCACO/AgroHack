<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import CartaoDeAlerta from '@/components/CartaoDeAlerta.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
import GraficoDeEstoque from '@/components/GraficoDeEstoque.vue'
import { buscarInsumo } from '@/services/estoque'
import { mensagemDeErro, useEstoqueStore } from '@/stores/estoque'
import type { InsumoDetalhe } from '@/types/api'

const props = defineProps<{ id: number }>()
const estoque = useEstoqueStore()
const router = useRouter()

const insumo = ref<InsumoDetalhe | null>(null)
const erro = ref<string | null>(null)

// `watch` e não `onMounted`: ir de um insumo a outro reaproveita a página.
watch(
  () => props.id,
  async (id) => {
    insumo.value = null
    erro.value = null
    try {
      insumo.value = await buscarInsumo(id)
      // A rota só sabe que é "Insumo"; a aba do navegador (e o leitor de tela) diz qual.
      document.title = `${insumo.value.nome} · CampoCerto`
    } catch (falha) {
      erro.value = mensagemDeErro(falha)
    }
  },
  { immediate: true },
)

async function remover() {
  if (!insumo.value) return
  const { id, nome, movimentacoes } = insumo.value
  const junto = movimentacoes.length ? ` e as ${movimentacoes.length} movimentações dele` : ''
  if (!window.confirm(`Remover ${nome}${junto}? Não dá para desfazer.`)) return
  try {
    await estoque.removerInsumo(id)
    await router.push({ name: 'insumos' })
  } catch (falha) {
    window.alert(mensagemDeErro(falha))
  }
}

const hoje = new Date().toLocaleDateString('sv-SE')
const numero = (valor: number, casas = 3) =>
  valor.toLocaleString('pt-BR', { maximumFractionDigits: casas })
const dataBr = (data: string) => data.split('-').reverse().join('/')

/** Os números que resumem o insumo. Quem calcula é a API; aqui só se formata. */
const resumo = computed(() => {
  if (!insumo.value) return []
  const { unidade, estoque_atual, analise } = insumo.value
  const { consumo_diario: consumo, cobertura_dias: cobertura, reposicao } = analise
  return [
    { rotulo: 'Estoque atual', valor: `${numero(estoque_atual)} ${unidade}` },
    { rotulo: 'Consumo médio', valor: consumo ? `${numero(consumo, 2)} ${unidade}/dia` : '—' },
    { rotulo: 'Dura cerca de', valor: cobertura === null ? '—' : `${Math.round(cobertura)} dias` },
    {
      rotulo: 'Reposição',
      valor: !reposicao
        ? 'nada a pedir'
        : reposicao.pedir_hoje
          ? 'pedir hoje'
          : `pedir até ${dataBr(reposicao.pedir_em)}`,
    },
  ]
})

const descricao = computed(() => {
  if (!insumo.value) return undefined
  const { unidade, estoque_minimo, prazo_reposicao_dias: prazo } = insumo.value
  const minimo = estoque_minimo === null ? 'sem mínimo' : `mínimo de ${numero(estoque_minimo)} ${unidade}`
  return `Em ${unidade}, ${minimo}, ${prazo === null ? 'sem prazo de entrega' : `entrega em ${prazo} dias`}.`
})
</script>

<template>
  <RouterLink
    :to="{ name: 'insumos' }"
    class="mb-3 inline-block text-sm font-medium text-campo-700 hover:underline"
  >
    ← Insumos
  </RouterLink>

  <p
    v-if="erro"
    role="alert"
    class="text-sm text-red-700"
  >
    {{ erro }}
  </p>

  <template v-else-if="insumo">
    <CabecalhoDePagina
      :titulo="insumo.nome"
      :descricao="descricao"
    >
      <template #acoes>
        <RouterLink
          :to="{ name: 'movimentacoes', query: { insumo: insumo.id } }"
          class="rounded-md bg-campo-600 px-4 py-2 text-sm font-medium text-white hover:bg-campo-700"
        >
          Lançar movimentação
        </RouterLink>
        <button
          type="button"
          class="rounded-md px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
          @click="remover"
        >
          Remover
        </button>
      </template>
    </CabecalhoDePagina>

    <dl class="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
      <div
        v-for="item in resumo"
        :key="item.rotulo"
        class="rounded-lg border border-stone-200 bg-white p-4"
      >
        <dt class="text-sm text-stone-500">
          {{ item.rotulo }}
        </dt>
        <dd class="mt-1 text-xl font-semibold text-stone-800">
          {{ item.valor }}
        </dd>
      </div>
    </dl>

    <EstadoVazio
      v-if="!insumo.historico.length"
      icone="movimentacoes"
      titulo="Nenhuma movimentação ainda"
      texto="Lance o estoque que já está no galpão como entrada, com a data de hoje, e as retiradas conforme acontecem."
    />

    <section
      v-else
      aria-labelledby="titulo-grafico"
      class="mt-6 rounded-lg border border-stone-200 bg-white p-4"
    >
      <h2
        id="titulo-grafico"
        class="font-semibold text-stone-800"
      >
        Estoque ao longo do tempo
      </h2>
      <p class="text-sm text-stone-500">
        Tracejado: para onde o estoque vai no ritmo de consumo atual.
      </p>
      <GraficoDeEstoque
        :insumo="insumo"
        :hoje="hoje"
        class="mt-2"
      />
    </section>

    <section
      aria-labelledby="titulo-alertas"
      class="mt-8"
    >
      <h2
        id="titulo-alertas"
        class="text-sm font-semibold uppercase tracking-wide text-stone-500"
      >
        Alertas
      </h2>
      <p
        v-if="!insumo.analise.alertas.length"
        class="mt-3 text-sm text-stone-600"
      >
        Nenhum alerta hoje.
      </p>
      <ul
        v-else
        class="mt-3 space-y-2"
      >
        <CartaoDeAlerta
          v-for="alerta in insumo.analise.alertas"
          :key="`${alerta.tipo}-${alerta.justificativa}`"
          :alerta="alerta"
        />
      </ul>
      <p
        v-if="insumo.analise.reposicao"
        class="mt-3 rounded-lg border border-stone-200 bg-white p-4 text-sm text-stone-700"
        data-teste="reposicao"
      >
        {{ insumo.analise.reposicao.justificativa }}
      </p>
    </section>

    <section
      aria-labelledby="titulo-limitacoes"
      class="mt-8"
    >
      <h2
        id="titulo-limitacoes"
        class="text-sm font-semibold uppercase tracking-wide text-stone-500"
      >
        Limitações da análise
      </h2>
      <ul class="mt-3 list-disc space-y-1 pl-5 text-sm text-stone-600">
        <li
          v-for="limitacao in insumo.analise.limitacoes"
          :key="limitacao"
        >
          {{ limitacao }}
        </li>
      </ul>
    </section>

    <!-- A tabela é a versão do gráfico para quem não o enxerga ou quer o número exato. -->
    <details
      v-if="insumo.movimentacoes.length"
      class="mt-8 rounded-lg border border-stone-200 bg-white"
    >
      <summary class="cursor-pointer px-4 py-3 text-sm font-medium text-stone-800">
        Movimentações ({{ insumo.movimentacoes.length }})
      </summary>
      <div class="overflow-x-auto border-t border-stone-100">
        <table class="w-full text-left text-sm">
          <thead class="bg-stone-50 text-xs uppercase tracking-wide text-stone-500">
            <tr>
              <th class="px-4 py-2 font-semibold">
                Data
              </th>
              <th class="px-4 py-2 font-semibold">
                Tipo
              </th>
              <th class="px-4 py-2 text-right font-semibold">
                Quantidade
              </th>
              <th class="px-4 py-2 font-semibold">
                Validade
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-stone-100">
            <tr
              v-for="mov in insumo.movimentacoes"
              :key="mov.id"
            >
              <td class="px-4 py-2 tabular-nums">
                {{ dataBr(mov.data) }}
              </td>
              <td
                class="px-4 py-2"
                :class="mov.tipo === 'entrada' ? 'text-campo-700' : 'text-terra-700'"
              >
                {{ mov.tipo === 'entrada' ? 'Entrada' : 'Saída' }}
              </td>
              <td class="px-4 py-2 text-right tabular-nums">
                {{ numero(mov.quantidade) }} {{ insumo.unidade }}
              </td>
              <td class="px-4 py-2 tabular-nums text-stone-600">
                {{ mov.validade ? dataBr(mov.validade) : '—' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>
  </template>
</template>
