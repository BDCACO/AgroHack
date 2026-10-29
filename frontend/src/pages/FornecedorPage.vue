<script setup lang="ts">
import { onMounted, ref } from 'vue'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import { dataBr, reais } from '@/formatos'
import * as api from '@/services/compras'
import { mensagemDeErro, useEstoqueStore } from '@/stores/estoque'
import type { FornecedorDetalhe } from '@/types/api'

const props = defineProps<{ id: number }>()
const estoque = useEstoqueStore()

const fornecedor = ref<FornecedorDetalhe | null>(null)
const erro = ref<string | null>(null)
onMounted(async () => {
  try {
    fornecedor.value = await api.buscarFornecedor(props.id)
  } catch (falha) {
    erro.value = mensagemDeErro(falha)
  }
})

const numero = (valor: number) => valor.toLocaleString('pt-BR', { maximumFractionDigits: 3 })
// A compra traz só o id do insumo: o nome vem dos preços dele (ou da lista de insumos).
const nomeDoInsumo = (id: number) =>
  fornecedor.value?.precos.find((preco) => preco.insumo_id === id)?.insumo ??
  estoque.insumoPorId.get(id)?.nome ??
  'Insumo'
const unidadeDoInsumo = (id: number) =>
  fornecedor.value?.precos.find((preco) => preco.insumo_id === id)?.unidade ??
  estoque.insumoPorId.get(id)?.unidade ??
  ''
</script>

<template>
  <RouterLink
    :to="{ name: 'fornecedores' }"
    class="mb-3 inline-flex text-sm font-medium text-campo-700 hover:underline"
  >
    ← Fornecedores
  </RouterLink>

  <p
    v-if="erro"
    role="alert"
    class="text-sm text-red-700"
  >
    {{ erro }}
  </p>

  <template v-else-if="fornecedor">
    <CabecalhoDePagina
      :titulo="fornecedor.nome"
      :descricao="[fornecedor.contato, fornecedor.telefone, fornecedor.cidade].filter(Boolean).join(' · ') || undefined"
    />
    <p
      v-if="!fornecedor.ativo"
      class="-mt-3 mb-4 text-sm text-stone-500"
    >
      Desativado: não aparece mais no pedido nem na compra.
    </p>

    <div class="grid animate-surgir gap-6 lg:grid-cols-2">
      <section class="cartao p-5">
        <h2 class="text-base font-semibold text-stone-900">
          Preço pago por insumo
        </h2>
        <p class="text-sm text-stone-500">
          A média das compras com preço, pesada pela quantidade.
        </p>
        <p
          v-if="!fornecedor.precos.length"
          class="mt-3 text-sm text-stone-500"
        >
          Nenhuma compra lançada com este fornecedor ainda.
        </p>
        <table
          v-else
          class="mt-3 w-full text-left text-sm"
        >
          <thead class="text-xs tracking-wide text-stone-500 uppercase">
            <tr>
              <th class="py-2 font-semibold">
                Insumo
              </th>
              <th class="py-2 text-right font-semibold">
                Comprado
              </th>
              <th class="py-2 text-right font-semibold">
                Preço médio
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-stone-100">
            <tr
              v-for="preco in fornecedor.precos"
              :key="preco.insumo_id"
              data-teste="preco-pago"
            >
              <td class="py-2 font-medium text-stone-800">
                <RouterLink
                  :to="{ name: 'insumo', params: { id: preco.insumo_id } }"
                  class="hover:text-campo-700 hover:underline"
                >
                  {{ preco.insumo }}
                </RouterLink>
                <span class="block text-xs font-normal text-stone-500">
                  {{ preco.compras === 1 ? '1 compra' : `${preco.compras} compras` }}
                </span>
              </td>
              <td class="py-2 text-right tabular-nums">
                {{ numero(preco.quantidade) }} {{ preco.unidade }}
              </td>
              <td class="py-2 text-right font-semibold tabular-nums">
                {{ preco.preco_medio === null ? '—' : `${reais(preco.preco_medio)}/${preco.unidade}` }}
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="cartao p-5">
        <h2 class="text-base font-semibold text-stone-900">
          Últimas compras
        </h2>
        <p
          v-if="!fornecedor.compras.length"
          class="mt-3 text-sm text-stone-500"
        >
          Nenhuma compra lançada com este fornecedor ainda.
        </p>
        <ul
          v-else
          class="mt-2 divide-y divide-stone-100"
        >
          <li
            v-for="compra in fornecedor.compras"
            :key="compra.id"
            class="flex items-center justify-between gap-3 py-2 text-sm"
            data-teste="compra"
          >
            <div class="min-w-0">
              <p class="font-medium text-stone-800">
                {{ nomeDoInsumo(compra.insumo_id) }}
              </p>
              <p class="text-xs text-stone-500">
                {{ dataBr(compra.data) }}<template v-if="compra.lancado_por">
                  · por {{ compra.lancado_por }}
                </template>
              </p>
            </div>
            <p class="text-right tabular-nums">
              {{ numero(compra.quantidade) }} {{ unidadeDoInsumo(compra.insumo_id) }}
              <span
                v-if="compra.valor_unitario"
                class="block text-xs text-stone-500"
              >{{ reais(compra.valor_unitario) }}/{{ unidadeDoInsumo(compra.insumo_id) }}</span>
            </p>
          </li>
        </ul>
      </section>
    </div>
  </template>
</template>
