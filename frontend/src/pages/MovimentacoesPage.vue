<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
import { mensagemDeErro, useEstoqueStore } from '@/stores/estoque'
import type { Movimentacao, MovimentacaoEntrada } from '@/types/api'

const estoque = useEstoqueStore()
onMounted(() => estoque.carregar())

// AAAA-MM-DD no fuso do navegador (o do produtor); 'sv-SE' formata exatamente assim.
const hoje = () => new Date().toLocaleDateString('sv-SE')

const form = reactive({
  tipo: 'saida' as MovimentacaoEntrada['tipo'],
  insumoId: '' as number | '',
  data: hoje(),
  quantidade: '' as number | '',
  validade: '',
})
const salvando = ref(false)
const erroDoForm = ref<string | null>(null)

// Validade é de lote, e lote só chega numa entrada.
watch(
  () => form.tipo,
  (tipo) => {
    if (tipo === 'saida') form.validade = ''
  },
)

async function lancar() {
  if (form.insumoId === '' || form.quantidade === '') return
  salvando.value = true
  erroDoForm.value = null
  try {
    await estoque.registrarMovimentacao({
      insumo_id: form.insumoId,
      tipo: form.tipo,
      data: form.data,
      quantidade: form.quantidade,
      validade: form.validade || null,
    })
    // Mantém tipo, insumo e data: lançamentos em sequência costumam repetir os três.
    form.quantidade = ''
    form.validade = ''
  } catch (erro) {
    erroDoForm.value = mensagemDeErro(erro)
  } finally {
    salvando.value = false
  }
}

async function remover(movimentacao: Movimentacao) {
  const insumo = estoque.insumoPorId.get(movimentacao.insumo_id)
  const resumo = `${rotulo[movimentacao.tipo].toLowerCase()} de ${numero(movimentacao.quantidade)} ${insumo?.unidade ?? ''} de ${insumo?.nome ?? 'insumo'}`
  if (!window.confirm(`Remover a ${resumo} em ${dataBr(movimentacao.data)}?`)) return
  try {
    await estoque.removerMovimentacao(movimentacao.id)
  } catch (erro) {
    window.alert(mensagemDeErro(erro))
  }
}

const rotulo = { entrada: 'Entrada', saida: 'Saída' } as const
const numero = (valor: number) => valor.toLocaleString('pt-BR', { maximumFractionDigits: 3 })
const dataBr = (data: string) => data.split('-').reverse().join('/')
</script>

<template>
  <CabecalhoDePagina
    titulo="Movimentações"
    descricao="Compras que chegaram (entradas) e retiradas do galpão (saídas). É daqui que sai o estoque e a análise de consumo."
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
    icone="movimentacoes"
    titulo="Cadastre um insumo primeiro"
    texto="Toda entrada ou saída é de um insumo. Cadastre os produtos do galpão e volte aqui para lançar o que entra e o que sai."
  >
    <RouterLink
      :to="{ name: 'insumos' }"
      class="inline-flex rounded-md bg-campo-600 px-4 py-2 text-sm font-medium text-white hover:bg-campo-700"
    >
      Ir para Insumos
    </RouterLink>
  </EstadoVazio>

  <template v-else-if="estoque.insumos.length">
    <form
      class="mt-6 grid gap-4 rounded-lg border border-stone-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-6"
      @submit.prevent="lancar"
    >
      <fieldset class="sm:col-span-2 lg:col-span-6">
        <legend class="text-sm font-medium text-stone-700">
          Tipo
        </legend>
        <div class="mt-1 inline-flex rounded-md border border-stone-300 p-0.5">
          <label
            v-for="tipo in (['saida', 'entrada'] as const)"
            :key="tipo"
            class="cursor-pointer rounded px-4 py-1.5 text-sm font-medium"
            :class="form.tipo === tipo ? 'bg-campo-600 text-white' : 'text-stone-700 hover:bg-stone-100'"
          >
            <input
              v-model="form.tipo"
              type="radio"
              name="tipo"
              :value="tipo"
              class="sr-only"
            >
            {{ tipo === 'saida' ? 'Saída (retirada)' : 'Entrada (compra)' }}
          </label>
        </div>
      </fieldset>
      <label class="text-sm font-medium text-stone-700 lg:col-span-2">
        Insumo
        <select
          v-model.number="form.insumoId"
          required
          class="campo"
        >
          <option
            value=""
            disabled
          >
            Escolha…
          </option>
          <option
            v-for="insumo in estoque.insumos"
            :key="insumo.id"
            :value="insumo.id"
          >
            {{ insumo.nome }} ({{ insumo.unidade }})
          </option>
        </select>
      </label>
      <label class="text-sm font-medium text-stone-700">
        Data
        <input
          v-model="form.data"
          type="date"
          required
          :max="hoje()"
          class="campo"
        >
      </label>
      <label class="text-sm font-medium text-stone-700">
        Quantidade
        <input
          v-model.number="form.quantidade"
          type="number"
          required
          min="0.001"
          step="any"
          class="campo"
        >
      </label>
      <label
        v-if="form.tipo === 'entrada'"
        class="text-sm font-medium text-stone-700 lg:col-span-2"
      >
        Validade do lote <span class="font-normal text-stone-500">(se tiver)</span>
        <input
          v-model="form.validade"
          type="date"
          class="campo"
        >
      </label>
      <p
        v-if="erroDoForm"
        role="alert"
        class="text-sm text-red-700 sm:col-span-2 lg:col-span-6"
      >
        {{ erroDoForm }}
      </p>
      <div class="sm:col-span-2 lg:col-span-6">
        <button
          type="submit"
          class="rounded-md bg-campo-600 px-4 py-2 text-sm font-medium text-white hover:bg-campo-700 disabled:opacity-50"
          :disabled="salvando"
        >
          {{ salvando ? 'Lançando…' : 'Lançar' }}
        </button>
      </div>
    </form>

    <p
      v-if="!estoque.movimentacoes.length"
      class="mt-6 text-sm text-stone-500"
    >
      Nenhuma movimentação lançada ainda. Comece pelo estoque que já está no galpão: lance como
      entrada, com a data de hoje.
    </p>
    <div
      v-else
      class="mt-6 overflow-x-auto rounded-lg border border-stone-200 bg-white"
    >
      <table class="w-full text-left text-sm">
        <caption class="sr-only">
          Últimas movimentações
        </caption>
        <thead class="bg-stone-50 text-xs uppercase tracking-wide text-stone-500">
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
            v-for="mov in estoque.movimentacoes"
            :key="mov.id"
          >
            <td class="px-4 py-3 tabular-nums">
              {{ dataBr(mov.data) }}
            </td>
            <td class="px-4 py-3 font-medium text-stone-800">
              {{ estoque.insumoPorId.get(mov.insumo_id)?.nome }}
            </td>
            <td
              class="px-4 py-3"
              :class="mov.tipo === 'entrada' ? 'text-campo-700' : 'text-terra-700'"
            >
              {{ rotulo[mov.tipo] }}
            </td>
            <td class="px-4 py-3 text-right tabular-nums">
              {{ numero(mov.quantidade) }} {{ estoque.insumoPorId.get(mov.insumo_id)?.unidade }}
            </td>
            <td class="px-4 py-3 tabular-nums text-stone-600">
              {{ mov.validade ? dataBr(mov.validade) : '—' }}
            </td>
            <td class="px-4 py-3 text-right">
              <button
                type="button"
                class="text-sm font-medium text-red-700 hover:underline"
                @click="remover(mov)"
              >
                Remover
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </template>
</template>
