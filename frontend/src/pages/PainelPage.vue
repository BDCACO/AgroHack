<script setup lang="ts">
import { computed, onMounted } from 'vue'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import CartaoDeAlerta from '@/components/CartaoDeAlerta.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
import SeloDeGravidade from '@/components/SeloDeGravidade.vue'
import { useEstoqueStore } from '@/stores/estoque'
import type { Gravidade } from '@/types/api'

// Só exibe: quem decide alerta, justificativa, reposição e limitação é o backend.
const estoque = useEstoqueStore()
onMounted(() => estoque.carregar())

const resumo = computed(() => {
  const contagem: Record<Gravidade, number> = { alta: 0, media: 0, baixa: 0 }
  for (const { alerta } of estoque.alertas) contagem[alerta.gravidade]++
  return [
    { gravidade: 'alta', titulo: 'Urgentes', total: contagem.alta },
    { gravidade: 'media', titulo: 'Atenção', total: contagem.media },
    { gravidade: 'baixa', titulo: 'Observar', total: contagem.baixa },
  ] as const
})

// Datas AAAA-MM-DD comparam certo como texto.
const reposicoes = computed(() =>
  estoque.insumos
    .flatMap((insumo) => (insumo.analise.reposicao ? [{ insumo, ...insumo.analise.reposicao }] : []))
    .sort((a, b) => a.pedir_em.localeCompare(b.pedir_em)),
)

const hoje = () => new Date().toLocaleDateString('sv-SE')
const dataBr = (data: string) => data.split('-').reverse().join('/')
</script>

<template>
  <CabecalhoDePagina
    titulo="Painel"
    descricao="Alertas sobre o estoque de insumos, com a justificativa de cada um."
  />

  <p
    v-if="estoque.erro"
    role="alert"
    class="mt-6 text-sm text-red-700"
  >
    {{ estoque.erro }}
  </p>

  <EstadoVazio
    v-else-if="estoque.carregado && !estoque.insumos.length"
    icone="insumos"
    titulo="Nenhum insumo cadastrado ainda"
    texto="Cadastre os insumos e lance as compras e retiradas: os alertas aparecem aqui, cada um com a conta que o justifica."
  >
    <RouterLink
      :to="{ name: 'insumos' }"
      class="inline-flex rounded-md bg-campo-600 px-4 py-2 text-sm font-medium text-white hover:bg-campo-700"
    >
      Cadastrar insumos
    </RouterLink>
  </EstadoVazio>

  <template v-else-if="estoque.insumos.length">
    <dl class="mt-6 grid grid-cols-3 gap-3">
      <div
        v-for="item in resumo"
        :key="item.gravidade"
        class="rounded-lg border border-stone-200 bg-white p-4"
      >
        <dt><SeloDeGravidade :gravidade="item.gravidade" /></dt>
        <dd class="mt-2 text-3xl font-semibold tabular-nums text-stone-800">
          {{ item.total }}
        </dd>
      </div>
    </dl>

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
        v-if="!estoque.alertas.length"
        class="mt-3 text-sm text-stone-600"
      >
        Nenhum alerta hoje. Os insumos estão dentro do esperado para o consumo registrado.
      </p>
      <ul
        v-else
        class="mt-3 space-y-2"
      >
        <CartaoDeAlerta
          v-for="{ insumo, alerta } in estoque.alertas"
          :key="`${insumo.id}-${alerta.tipo}-${alerta.justificativa}`"
          :alerta="alerta"
          :insumo="insumo"
        />
      </ul>
    </section>

    <section
      v-if="reposicoes.length"
      aria-labelledby="titulo-reposicao"
      class="mt-8"
    >
      <h2
        id="titulo-reposicao"
        class="text-sm font-semibold uppercase tracking-wide text-stone-500"
      >
        Reposição estimada
      </h2>
      <ul class="mt-3 divide-y divide-stone-100 rounded-lg border border-stone-200 bg-white">
        <li
          v-for="item in reposicoes"
          :key="item.insumo.id"
          class="p-4"
          data-teste="reposicao"
        >
          <p class="font-medium text-stone-800">
            <RouterLink
              :to="{ name: 'insumo', params: { id: item.insumo.id } }"
              class="hover:text-campo-700 hover:underline"
            >
              {{ item.insumo.nome }}
            </RouterLink>
            <span
              class="ml-2 text-sm font-normal"
              :class="item.pedir_em <= hoje() ? 'text-red-700' : 'text-stone-500'"
            >
              {{ item.pedir_em <= hoje() ? 'pedir hoje' : `pedir até ${dataBr(item.pedir_em)}` }}
            </span>
          </p>
          <p class="mt-0.5 text-sm text-stone-600">
            {{ item.justificativa }}
          </p>
        </li>
      </ul>
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
      <p class="mt-1 text-sm text-stone-500">
        O que a conta não sabe, por insumo. Leia antes de decidir uma compra.
      </p>
      <div class="mt-3 divide-y divide-stone-100 rounded-lg border border-stone-200 bg-white">
        <details
          v-for="insumo in estoque.insumos"
          :key="insumo.id"
          class="px-4 py-3"
        >
          <summary class="cursor-pointer text-sm font-medium text-stone-800">
            {{ insumo.nome }}
            <span class="font-normal text-stone-500">({{ insumo.analise.limitacoes.length }})</span>
          </summary>
          <ul class="mt-2 list-disc space-y-1 pl-5 text-sm text-stone-600">
            <li
              v-for="limitacao in insumo.analise.limitacoes"
              :key="limitacao"
            >
              {{ limitacao }}
            </li>
          </ul>
        </details>
      </div>
    </section>
  </template>
</template>
