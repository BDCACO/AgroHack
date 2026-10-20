<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import CartaoDeAlerta from '@/components/CartaoDeAlerta.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
import GraficoDeEstoque from '@/components/GraficoDeEstoque.vue'
import IconeSvg from '@/components/IconeSvg.vue'
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
const resumo = computed((): { rotulo: string; valor: string; alerta?: boolean }[] => {
  if (!insumo.value) return []
  const { unidade, estoque_atual, analise } = insumo.value
  const { consumo_diario: consumo, cobertura_dias: cobertura, reposicao } = analise
  return [
    { rotulo: 'Estoque atual', valor: `${numero(estoque_atual)} ${unidade}` },
    { rotulo: 'Consumo médio', valor: consumo ? `${numero(consumo, 2)} ${unidade}/dia` : '—' },
    { rotulo: 'Dura cerca de', valor: cobertura === null ? '—' : `${numero(Math.round(cobertura))} dias` },
    {
      rotulo: 'Reposição',
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
    class="group mb-6 inline-flex items-center gap-1 text-sm text-tinta-3 transition-colors duration-150 hover:text-tinta"
  >
    <IconeSvg
      nome="seta"
      class="size-4 rotate-180 transition-transform duration-200 ease-chegar group-hover:-translate-x-0.5"
    />
    Insumos
  </RouterLink>

  <p
    v-if="erro"
    role="alert"
    class="border-l-2 border-urgente pl-3 text-sm text-urgente"
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

    <dl class="grid grid-cols-2 border-t border-l border-linha lg:grid-cols-4">
      <div
        v-for="(item, indice) in resumo"
        :key="item.rotulo"
        class="animate-surgir border-r border-b border-linha px-4 py-5 sm:px-5"
        :style="{ animationDelay: `${indice * 40}ms` }"
      >
        <dt
          class="text-sm"
          :class="item.alerta ? 'text-urgente' : 'text-tinta-3'"
        >
          {{ item.rotulo }}
        </dt>
        <dd
          class="mt-2 font-serif text-[1.625rem] leading-none tabular-nums"
          :class="item.alerta ? 'text-urgente' : 'text-tinta'"
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
      class="mt-12 animate-surgir [animation-delay:120ms]"
    >
      <h2
        id="titulo-grafico"
        class="titulo-secao"
      >
        Estoque ao longo do tempo
      </h2>
      <p class="mt-1 text-sm text-tinta-3">
        A linha tracejada projeta o consumo atual até o estoque zerar.
      </p>
      <GraficoDeEstoque
        :insumo="insumo"
        :hoje="hoje"
        class="mt-4 border-y border-linha py-3"
      />
    </section>

    <section
      aria-labelledby="titulo-alertas"
      class="mt-12"
    >
      <h2
        id="titulo-alertas"
        class="titulo-secao"
      >
        Alertas
      </h2>
      <p
        v-if="!insumo.analise.alertas.length"
        class="mt-4 border-y border-linha py-5 text-sm text-tinta-2"
      >
        Nenhum alerta hoje.
      </p>
      <ul
        v-else
        class="mt-4 divide-y divide-linha border-y border-linha"
      >
        <CartaoDeAlerta
          v-for="alerta in insumo.analise.alertas"
          :key="`${alerta.tipo}-${alerta.justificativa}`"
          :alerta="alerta"
        />
      </ul>
      <p
        v-if="insumo.analise.reposicao"
        class="mt-5 border-l-2 border-atencao-forte pl-3 text-sm leading-relaxed text-tinta"
        data-teste="reposicao"
      >
        {{ insumo.analise.reposicao.justificativa }}
      </p>
    </section>

    <section
      aria-labelledby="titulo-limitacoes"
      class="mt-12"
    >
      <h2
        id="titulo-limitacoes"
        class="titulo-secao"
      >
        Limitações da análise
      </h2>
      <ul class="mt-4 list-disc space-y-1 pl-5 text-sm leading-relaxed text-tinta-2">
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
      class="group mt-12 border-y border-linha"
    >
      <summary class="flex cursor-pointer list-none items-center justify-between gap-2 py-3 text-sm font-medium text-tinta transition-colors duration-150 hover:text-campo-700 [&::-webkit-details-marker]:hidden">
        <span>
          Movimentações
          <span class="ml-1 font-normal text-tinta-3 tabular-nums">{{ insumo.movimentacoes.length }}</span>
        </span>
        <IconeSvg
          nome="seta"
          class="size-4 text-tinta-3 transition-transform duration-200 ease-mover group-open:rotate-90"
        />
      </summary>
      <div class="animate-surgir overflow-x-auto border-t border-linha">
        <table class="w-full text-left text-sm">
          <thead class="text-xs text-tinta-3">
            <tr>
              <th class="px-0 py-2 pr-4 font-medium">
                Data
              </th>
              <th class="px-0 py-2 pr-4 font-medium">
                Tipo
              </th>
              <th class="px-0 py-2 pr-4 text-right font-medium">
                Quantidade
              </th>
              <th class="px-0 py-2 pr-4 font-medium">
                Validade
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-linha">
            <tr
              v-for="mov in insumo.movimentacoes"
              :key="mov.id"
            >
              <td class="py-2 pr-4 tabular-nums">
                {{ dataBr(mov.data) }}
              </td>
              <td
                class="py-2 pr-4"
                :class="mov.tipo === 'entrada' ? 'text-campo-700' : 'text-terra-700'"
              >
                {{ mov.tipo === 'entrada' ? 'Entrada' : 'Saída' }}
              </td>
              <td class="py-2 pr-4 text-right tabular-nums">
                {{ numero(mov.quantidade) }} {{ insumo.unidade }}
              </td>
              <td class="py-2 pr-4 tabular-nums text-tinta-2">
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
        class="esqueleto h-24 rounded-md"
      />
    </div>
    <div class="esqueleto mt-6 h-80 rounded-md" />
  </div>
</template>
