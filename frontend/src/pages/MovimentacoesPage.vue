<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import AvisoDeErro from '@/components/AvisoDeErro.vue'
import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import ConfirmarRemocao from '@/components/ConfirmarRemocao.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
import FormularioMovimentacao from '@/components/FormularioMovimentacao.vue'
import JanelaModal from '@/components/JanelaModal.vue'
import { formatarData, formatarQuantidade } from '@/formatos'
import { useInsumosStore } from '@/stores/insumos'
import { useMovimentacoesStore } from '@/stores/movimentacoes'
import type { Movimentacao } from '@/types/api'

const insumos = useInsumosStore()
const movimentacoes = useMovimentacoesStore()

const formularioAberto = ref(false)
const emRemocao = ref<Movimentacao | null>(null)

const filtro = computed({
  get: () => movimentacoes.filtroInsumoId ?? '',
  set: (valor: string) => movimentacoes.filtrar(valor || null),
})

const semInsumos = computed(() => !insumos.carregando && insumos.lista.length === 0)

onMounted(() => Promise.all([insumos.carregar(), movimentacoes.carregar()]))
</script>

<template>
  <CabecalhoDePagina
    titulo="Movimentações"
    descricao="Compras e retiradas de insumos. Cada registro atualiza o saldo do insumo."
  >
    <template #acoes>
      <button
        type="button"
        class="botao-primario"
        :disabled="semInsumos"
        @click="formularioAberto = true"
      >
        Registrar movimentação
      </button>
    </template>
  </CabecalhoDePagina>

  <EstadoVazio
    v-if="semInsumos"
    icone="insumos"
    titulo="Cadastre um insumo primeiro"
    texto="Toda compra ou retirada é de um insumo. Cadastre os produtos e depois registre as movimentações."
  >
    <RouterLink
      :to="{ name: 'insumos' }"
      class="botao-primario"
    >
      Ir para Insumos
    </RouterLink>
  </EstadoVazio>

  <template v-else>
    <div class="mt-6 max-w-xs">
      <label
        for="filtro-insumo"
        class="rotulo"
      >Filtrar por insumo</label>
      <select
        id="filtro-insumo"
        v-model="filtro"
        class="campo"
      >
        <option value="">
          Todos os insumos
        </option>
        <option
          v-for="insumo in insumos.lista"
          :key="insumo.id"
          :value="insumo.id"
        >
          {{ insumo.nome }}
        </option>
      </select>
    </div>

    <AvisoDeErro
      v-if="movimentacoes.erro"
      class="mt-6"
      :mensagem="movimentacoes.erro"
    />

    <EstadoVazio
      v-else-if="!movimentacoes.carregando && movimentacoes.lista.length === 0"
      icone="movimentacoes"
      titulo="Nenhuma movimentação registrada"
      texto="Registre as compras e retiradas para acompanhar o saldo e o consumo de cada insumo."
    />

    <div
      v-else
      class="relative mt-4 overflow-x-auto rounded-lg border border-stone-200 bg-white"
    >
      <table class="w-full min-w-[44rem] text-left text-sm">
        <thead class="border-b border-stone-200 bg-stone-50 text-xs uppercase tracking-wide text-stone-500">
          <tr>
            <th class="px-4 py-3 font-semibold">
              Data
            </th>
            <th class="px-4 py-3 font-semibold">
              Insumo
            </th>
            <th class="px-4 py-3 font-semibold">
              Tipo
            </th>
            <th class="px-4 py-3 text-right font-semibold">
              Quantidade
            </th>
            <th class="px-4 py-3 font-semibold">
              Validade
            </th>
            <th class="px-4 py-3">
              <span class="sr-only">Ações</span>
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-stone-100">
          <tr
            v-for="mov in movimentacoes.lista"
            :key="mov.id"
            class="hover:bg-stone-50"
          >
            <td class="px-4 py-3 whitespace-nowrap tabular-nums">
              {{ formatarData(mov.data) }}
            </td>
            <td class="px-4 py-3">
              <p class="font-medium text-stone-900">
                {{ mov.insumo_nome }}
              </p>
              <p
                v-if="mov.observacao"
                class="text-xs text-stone-500"
              >
                {{ mov.observacao }}
              </p>
            </td>
            <td class="px-4 py-3">
              <span
                class="inline-flex rounded-full px-2 py-0.5 text-xs font-medium"
                :class="mov.tipo === 'compra' ? 'bg-campo-100 text-campo-900' : 'bg-terra-100 text-terra-700'"
              >
                {{ mov.tipo === 'compra' ? 'Compra' : 'Retirada' }}
              </span>
            </td>
            <td class="px-4 py-3 text-right whitespace-nowrap tabular-nums">
              {{ mov.tipo === 'compra' ? '+' : '−' }}{{ formatarQuantidade(mov.quantidade) }}
              {{ mov.insumo_unidade }}
            </td>
            <td class="px-4 py-3 whitespace-nowrap tabular-nums text-stone-600">
              {{ mov.validade ? formatarData(mov.validade) : '—' }}
            </td>
            <td class="px-4 py-3 text-right">
              <button
                type="button"
                class="botao-link text-red-700 hover:bg-red-50"
                @click="emRemocao = mov"
              >
                Remover
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </template>

  <JanelaModal
    v-if="formularioAberto"
    titulo="Registrar movimentação"
    @fechar="formularioAberto = false"
  >
    <FormularioMovimentacao
      :insumo-inicial-id="movimentacoes.filtroInsumoId"
      @salvo="formularioAberto = false"
      @cancelar="formularioAberto = false"
    />
  </JanelaModal>

  <ConfirmarRemocao
    v-if="emRemocao"
    titulo="Remover movimentação"
    :texto="`Remover a ${emRemocao.tipo} de ${formatarQuantidade(emRemocao.quantidade)} ${emRemocao.insumo_unidade} de ${emRemocao.insumo_nome} em ${formatarData(emRemocao.data)}? O saldo do insumo será recalculado.`"
    :remover="() => movimentacoes.remover(emRemocao!.id)"
    @fechar="emRemocao = null"
  />
</template>
