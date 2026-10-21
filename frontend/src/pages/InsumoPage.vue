<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import CartaoDeAlerta from '@/components/CartaoDeAlerta.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
import GraficoDeEstoque from '@/components/GraficoDeEstoque.vue'
import IconeSvg, { type NomeIcone } from '@/components/IconeSvg.vue'
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
const resumo = computed((): { rotulo: string; valor: string; icone: NomeIcone; alerta?: boolean }[] => {
  if (!insumo.value) return []
  const { unidade, estoque_atual, analise } = insumo.value
  const { consumo_diario: consumo, cobertura_dias: cobertura, reposicao } = analise
  return [
    { rotulo: 'Estoque atual', valor: `${numero(estoque_atual)} ${unidade}`, icone: 'insumos' },
    { rotulo: 'Consumo médio', valor: consumo ? `${numero(consumo, 2)} ${unidade}/dia` : '—', icone: 'movimentacoes' },
    { rotulo: 'Dura cerca de', valor: cobertura === null ? '—' : `${numero(Math.round(cobertura))} dias`, icone: 'relogio' },
    {
      rotulo: 'Reposição',
      icone: 'calendario',
      alerta: Boolean(reposicao?.pedir_hoje),
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
    class="group mb-4 inline-flex items-center gap-1 text-sm font-semibold text-campo-700 hover:text-campo-900"
  >
    <IconeSvg
      nome="seta"
      class="h-4 w-4 rotate-180 transition-transform duration-200 ease-chegada group-hover:-translate-x-1"
    />
    Insumos
  </RouterLink>

  <p
    v-if="erro"
    role="alert"
    class="cartao border-red-200 bg-red-50 p-4 text-sm text-red-800"
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
          class="botao-primario"
        >
          Lançar movimentação
        </RouterLink>
        <button
          type="button"
          class="botao-perigo"
          @click="remover"
        >
          Remover
        </button>
      </template>
    </CabecalhoDePagina>

    <dl class="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <div
        v-for="(item, indice) in resumo"
        :key="item.rotulo"
        class="cartao animate-surgir p-4"
        :class="item.alerta ? 'border-red-200 bg-red-50/60' : ''"
        :style="{ animationDelay: `${indice * 60}ms` }"
      >
        <dt
          class="flex items-center gap-2 text-sm"
          :class="item.alerta ? 'text-red-800' : 'text-stone-500'"
        >
          <span
            class="rounded-lg p-1.5"
            :class="item.alerta ? 'bg-red-100 text-red-600' : 'bg-campo-50 text-campo-600'"
            aria-hidden="true"
          >
            <IconeSvg
              :nome="item.icone"
              class="h-4 w-4"
            />
          </span>
          {{ item.rotulo }}
        </dt>
        <dd
          class="mt-2 text-xl font-bold"
          :class="item.alerta ? 'text-red-700' : 'text-stone-900'"
        >
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
      class="cartao mt-6 animate-surgir p-5 [animation-delay:200ms]"
    >
      <h2
        id="titulo-grafico"
        class="text-base font-semibold text-stone-900"
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
        class="text-base font-semibold text-stone-900"
      >
        Alertas
      </h2>
      <p
        v-if="!insumo.analise.alertas.length"
        class="cartao mt-3 p-4 text-sm text-stone-600"
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
        class="cartao mt-3 border-amber-200 bg-amber-50/60 p-4 text-sm text-stone-800"
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
        class="text-base font-semibold text-stone-900"
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
      class="cartao group mt-8 overflow-hidden"
    >
      <summary class="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm font-semibold text-stone-800 [&::-webkit-details-marker]:hidden">
        <IconeSvg
          nome="seta"
          class="h-4 w-4 text-stone-400 transition-transform duration-200 ease-movimento group-open:rotate-90"
        />
        Movimentações ({{ insumo.movimentacoes.length }})
      </summary>
      <div class="overflow-x-auto border-t border-stone-100">
        <table class="w-full text-left text-sm">
          <thead class="bg-stone-50/80 text-xs tracking-wide text-stone-500 uppercase">
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
              <!-- No celular, a validade vai para baixo do tipo: quatro colunas não cabem. -->
              <th class="px-4 py-2 font-semibold max-sm:hidden">
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
                <span
                  v-if="mov.validade"
                  class="block text-xs text-stone-500 tabular-nums sm:hidden"
                >val. {{ dataBr(mov.validade) }}</span>
              </td>
              <td class="px-4 py-2 text-right tabular-nums">
                {{ numero(mov.quantidade) }} {{ insumo.unidade }}
              </td>
              <td class="px-4 py-2 tabular-nums text-stone-600 max-sm:hidden">
                {{ mov.validade ? dataBr(mov.validade) : '—' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>
  </template>

  <!-- Esqueleto: a forma da página enquanto o insumo chega. -->
  <div
    v-else
    aria-busy="true"
    aria-label="Carregando o insumo"
  >
    <div class="esqueleto h-9 w-64" />
    <div class="esqueleto mt-3 h-5 w-96 max-w-full" />
    <div class="mt-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
      <div
        v-for="n in 4"
        :key="n"
        class="esqueleto h-24 rounded-xl"
      />
    </div>
    <div class="esqueleto mt-6 h-80 rounded-xl" />
  </div>
</template>
