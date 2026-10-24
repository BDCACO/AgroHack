<script setup lang="ts">
import { onMounted, ref } from 'vue'

import AvisoDeErro from '@/components/AvisoDeErro.vue'
import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import ConfirmarRemocao from '@/components/ConfirmarRemocao.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
import FormularioInsumo from '@/components/FormularioInsumo.vue'
import JanelaModal from '@/components/JanelaModal.vue'
import { formatarQuantidade } from '@/formatos'
import { useInsumosStore } from '@/stores/insumos'
import type { Insumo } from '@/types/api'

const insumos = useInsumosStore()

// undefined = formulário fechado; null = novo; Insumo = edição.
const emEdicao = ref<Insumo | null | undefined>(undefined)
const emRemocao = ref<Insumo | null>(null)

onMounted(() => insumos.carregar())
</script>

<template>
  <CabecalhoDePagina
    titulo="Insumos"
    descricao="Produtos em estoque. O saldo é calculado a partir das compras e retiradas registradas."
  >
    <template #acoes>
      <button
        type="button"
        class="botao-primario"
        @click="emEdicao = null"
      >
        Novo insumo
      </button>
    </template>
  </CabecalhoDePagina>

  <AvisoDeErro
    v-if="insumos.erro"
    class="mt-6"
    :mensagem="insumos.erro"
  />

  <p
    v-else-if="insumos.carregando && insumos.lista.length === 0"
    class="mt-6 text-sm text-stone-500"
  >
    Carregando…
  </p>

  <EstadoVazio
    v-else-if="insumos.lista.length === 0"
    icone="insumos"
    titulo="Nenhum insumo cadastrado"
    texto="Cadastre os produtos que você compra e usa na propriedade: fertilizantes, defensivos, sementes, rações…"
  >
    <button
      type="button"
      class="botao-primario"
      @click="emEdicao = null"
    >
      Cadastrar o primeiro insumo
    </button>
  </EstadoVazio>

  <div
    v-else
    class="relative mt-6 overflow-x-auto rounded-lg border border-stone-200 bg-white"
  >
    <table class="w-full min-w-[36rem] text-left text-sm">
      <thead class="border-b border-stone-200 bg-stone-50 text-xs uppercase tracking-wide text-stone-500">
        <tr>
          <th class="px-4 py-3 font-semibold">
            Insumo
          </th>
          <th class="px-4 py-3 text-right font-semibold">
            Saldo atual
          </th>
          <th class="px-4 py-3 text-right font-semibold">
            Estoque mínimo
          </th>
          <th class="px-4 py-3">
            <span class="sr-only">Ações</span>
          </th>
        </tr>
      </thead>
      <tbody class="divide-y divide-stone-100">
        <tr
          v-for="insumo in insumos.lista"
          :key="insumo.id"
          class="hover:bg-stone-50"
        >
          <td class="px-4 py-3">
            <p class="font-medium text-stone-900">
              {{ insumo.nome }}
            </p>
            <p
              v-if="insumo.categoria"
              class="text-xs text-stone-500"
            >
              {{ insumo.categoria }}
            </p>
          </td>
          <td class="px-4 py-3 text-right tabular-nums">
            {{ formatarQuantidade(insumo.saldo_atual) }} {{ insumo.unidade }}
          </td>
          <td class="px-4 py-3 text-right tabular-nums text-stone-600">
            {{ formatarQuantidade(insumo.estoque_minimo) }} {{ insumo.unidade }}
          </td>
          <td class="px-4 py-3 text-right whitespace-nowrap">
            <button
              type="button"
              class="botao-link"
              @click="emEdicao = insumo"
            >
              Editar
            </button>
            <button
              type="button"
              class="botao-link text-red-700 hover:bg-red-50"
              @click="emRemocao = insumo"
            >
              Remover
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <JanelaModal
    v-if="emEdicao !== undefined"
    :titulo="emEdicao ? 'Editar insumo' : 'Novo insumo'"
    @fechar="emEdicao = undefined"
  >
    <FormularioInsumo
      :insumo="emEdicao"
      @salvo="emEdicao = undefined"
      @cancelar="emEdicao = undefined"
    />
  </JanelaModal>

  <ConfirmarRemocao
    v-if="emRemocao"
    titulo="Remover insumo"
    :texto="`Remover “${emRemocao.nome}”? Só é possível remover insumos sem movimentações registradas.`"
    :remover="() => insumos.remover(emRemocao!.id)"
    @fechar="emRemocao = null"
  />
</template>
