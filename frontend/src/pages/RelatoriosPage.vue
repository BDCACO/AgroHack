<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'

import BotaoDeDownload from '@/components/BotaoDeDownload.vue'
import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import GraficoPorPeriodo from '@/components/GraficoPorPeriodo.vue'
import { dataBr, reais } from '@/formatos'
import { baixarRelatorioPorPeriodo, buscarRelatorioPorPeriodo } from '@/services/relatorios'
import { useCategoriasStore } from '@/stores/categorias'
import { mensagemDeErro, useEstoqueStore } from '@/stores/estoque'
import { useFornecedoresStore } from '@/stores/fornecedores'
import type { Agrupamento, FiltroDoRelatorio, RelatorioPorPeriodo } from '@/types/api'

// Só exibe: cada soma vem da API, com as mesmas regras do custo médio e do Excel.
const estoque = useEstoqueStore()
const fornecedores = useFornecedoresStore()
const categorias = useCategoriasStore()

const filtro = reactive<Required<FiltroDoRelatorio>>({
  desde: '',
  ate: '',
  agrupar: 'mes',
  categoria_id: '',
  insumo_id: '',
  fornecedor_id: '',
})
const relatorio = ref<RelatorioPorPeriodo | null>(null)
// O arquivo sai com os filtros da tela: o que se baixa é o que se vê.
const baixarPdf = () => baixarRelatorioPorPeriodo({ ...filtro }, 'pdf')
const baixarExcel = () => baixarRelatorioPorPeriodo({ ...filtro }, 'xlsx')
const carregando = ref(false)
const erro = ref<string | null>(null)

// Filtro trocado de novo antes de a resposta chegar: só a última vale.
let pedido = 0
async function carregar() {
  const este = ++pedido
  carregando.value = true
  erro.value = null
  try {
    const resposta = await buscarRelatorioPorPeriodo({ ...filtro })
    if (este === pedido) relatorio.value = resposta
  } catch (falha) {
    if (este === pedido) erro.value = mensagemDeErro(falha)
  } finally {
    if (este === pedido) carregando.value = false
  }
}
onMounted(() => Promise.all([carregar(), fornecedores.carregar(), categorias.carregar()]))
watch(filtro, carregar)

const agrupamentos: { valor: Agrupamento; rotulo: string }[] = [
  { valor: 'mes', rotulo: 'Por mês' },
  { valor: 'semana', rotulo: 'Por semana' },
  { valor: 'dia', rotulo: 'Por dia' },
]

const consumoEmReais = computed(
  () => relatorio.value?.total.consumo.reduce((soma, item) => soma + (item.valor ?? 0), 0) ?? 0,
)
// O que mais custou primeiro: é por onde se começa a cortar.
const consumoPorInsumo = computed(() =>
  [...(relatorio.value?.total.consumo ?? [])]
    .filter((item) => item.quantidade > 0)
    .sort((a, b) => (b.valor ?? -1) - (a.valor ?? -1)),
)
const porCategoria = computed(() =>
  (relatorio.value?.total.por_categoria ?? []).filter((c) => c.gasto || c.consumo || c.perdas),
)
const porFornecedor = computed(() => (relatorio.value?.total.por_fornecedor ?? []).filter((f) => f.compras))

const numero = (valor: number) => valor.toLocaleString('pt-BR', { maximumFractionDigits: 2 })
const plural = (n: number, um: string, varios: string) => (n === 1 ? `1 ${um}` : `${n} ${varios}`)
</script>

<template>
  <CabecalhoDePagina
    titulo="Relatórios"
  >
    <template #acoes>
      <BotaoDeDownload
        rotulo="Baixar PDF"
        :baixar="baixarPdf"
        class="botao-secundario"
        data-teste="baixar-pdf"
      />
      <BotaoDeDownload
        rotulo="Baixar Excel"
        :baixar="baixarExcel"
        class="botao-primario"
        data-teste="baixar-excel"
      />
    </template>
  </CabecalhoDePagina>

  <form
    class="cartao mb-6 grid animate-surgir gap-4 p-5 sm:grid-cols-3 xl:grid-cols-6"
    aria-label="Filtros do relatório"
    @submit.prevent
  >
    <label class="flutuante">
      <input
        v-model="filtro.desde"
        type="date"
        :max="filtro.ate || undefined"
        class="campo"
        data-teste="desde"
      >
      <span class="rotulo">De <span class="font-normal text-stone-500">(vazio: 12 meses)</span></span>
    </label>
    <label class="flutuante">
      <input
        v-model="filtro.ate"
        type="date"
        :min="filtro.desde || undefined"
        class="campo"
        data-teste="ate"
      >
      <span class="rotulo">Até <span class="font-normal text-stone-500">(vazio: hoje)</span></span>
    </label>
    <label class="flutuante">
      <select
        v-model="filtro.agrupar"
        class="campo"
        data-teste="agrupar"
      >
        <option
          v-for="opcao in agrupamentos"
          :key="opcao.valor"
          :value="opcao.valor"
        >
          {{ opcao.rotulo }}
        </option>
      </select>
      <span class="rotulo">Agrupar</span>
    </label>
    <label class="flutuante">
      <select
        v-model.number="filtro.categoria_id"
        class="campo"
        data-teste="filtro-categoria"
      >
        <option value="">
          Todas
        </option>
        <option
          v-for="categoria in categorias.categorias"
          :key="categoria.id"
          :value="categoria.id"
        >
          {{ categoria.nome }}
        </option>
      </select>
      <span class="rotulo">Categoria</span>
    </label>
    <label class="flutuante">
      <select
        v-model.number="filtro.insumo_id"
        class="campo"
        data-teste="insumo"
      >
        <option value="">
          Todos
        </option>
        <option
          v-for="insumo in estoque.insumos"
          :key="insumo.id"
          :value="insumo.id"
        >
          {{ insumo.nome }}
        </option>
      </select>
      <span class="rotulo">Insumo</span>
    </label>
    <label class="flutuante">
      <select
        v-model.number="filtro.fornecedor_id"
        class="campo"
        data-teste="fornecedor"
      >
        <option value="">
          Todos
        </option>
        <option
          v-for="fornecedor in fornecedores.fornecedores"
          :key="fornecedor.id"
          :value="fornecedor.id"
        >
          {{ fornecedor.nome }}
        </option>
      </select>
      <span class="rotulo">Fornecedor</span>
    </label>
  </form>

  <p
    v-if="erro"
    role="alert"
    class="text-sm text-red-700"
    data-teste="erro"
  >
    {{ erro }}
  </p>

  <template v-else-if="relatorio">
    <p
      class="mb-3 text-sm text-stone-600"
      :class="carregando ? 'opacity-60' : ''"
      data-teste="intervalo"
    >
      De {{ dataBr(relatorio.desde) }} a {{ dataBr(relatorio.ate) }}
    </p>

    <div
      class="grid animate-surgir gap-3 sm:grid-cols-3"
      :class="carregando ? 'opacity-60' : ''"
    >
      <div
        class="cartao border-t-4 border-t-campo-600 p-4"
        data-teste="total-gasto"
      >
        <p class="text-sm text-stone-500">
          Gasto em compras
        </p>
        <p class="text-2xl font-bold text-stone-900 tabular-nums">
          {{ reais(relatorio.total.gasto) }}
        </p>
        <p
          v-if="relatorio.total.compras_sem_preco"
          class="text-xs text-amber-800"
        >
          Fora da conta: {{ plural(relatorio.total.compras_sem_preco, 'compra sem preço', 'compras sem preço') }}
        </p>
      </div>
      <div
        class="cartao border-t-4 border-t-terra-500 p-4"
        data-teste="total-consumo"
      >
        <p class="text-sm text-stone-500">
          Consumo
        </p>
        <p class="text-2xl font-bold text-stone-900 tabular-nums">
          {{ reais(consumoEmReais) }}
        </p>
        <p class="text-xs text-stone-500">
          O que se usou, pelo custo médio
        </p>
      </div>
      <div
        class="cartao border-t-4 border-t-red-600 p-4"
        data-teste="total-perdas"
      >
        <p class="text-sm text-stone-500">
          Perdas
        </p>
        <p class="text-2xl font-bold text-stone-900 tabular-nums">
          {{ reais(relatorio.total.perdas) }}
        </p>
        <p class="text-xs text-stone-500">
          Descartes e faltas da contagem<template v-if="relatorio.total.perdas_sem_preco">
            · fora da conta: {{ plural(relatorio.total.perdas_sem_preco, 'perda de insumo sem preço', 'perdas de insumo sem preço') }}
          </template>
        </p>
      </div>
    </div>

    <section class="cartao mt-6 p-4 sm:p-5">
      <h2 class="text-base font-semibold text-stone-900">
        {{ agrupamentos.find((a) => a.valor === relatorio!.agrupar)?.rotulo }}
      </h2>
      <GraficoPorPeriodo :periodos="relatorio.periodos" />
    </section>

    <!-- grid-cols-1, e não a coluna automática: no celular, o cartão cabe na tela e o nome
         quebra a linha, em vez de a tabela empurrar a página para o lado. -->
    <div class="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
      <section class="cartao p-5">
        <h2 class="text-base font-semibold text-stone-900">
          Consumo por insumo
        </h2>
        <p
          v-if="!consumoPorInsumo.length"
          class="mt-2 text-sm text-stone-500"
        >
          Nenhuma retirada para uso no período.
        </p>
        <table
          v-else
          class="mt-2 w-full text-left text-sm"
        >
          <tbody class="divide-y divide-stone-100">
            <tr
              v-for="item in consumoPorInsumo"
              :key="item.insumo_id"
              data-teste="consumo-insumo"
            >
              <td class="py-2 font-medium text-stone-800">
                {{ item.insumo }}
              </td>
              <td class="py-2 pl-3 text-right whitespace-nowrap tabular-nums">
                {{ numero(item.quantidade) }} {{ item.unidade }}
              </td>
              <td class="py-2 pl-3 text-right font-semibold whitespace-nowrap tabular-nums">
                {{ item.valor === null ? '—' : reais(item.valor) }}
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="cartao p-5">
        <h2 class="text-base font-semibold text-stone-900">
          Por categoria
        </h2>
        <p
          v-if="!porCategoria.length"
          class="mt-2 text-sm text-stone-500"
        >
          Nada no período.
        </p>
        <!-- Quatro colunas em reais não cabem num celular pequeno: a tabela rola de lado
             dentro do cartão, e a página não. -->
        <div
          v-else
          class="-mx-5 mt-2 overflow-x-auto px-5"
        >
          <table class="w-full text-left text-sm whitespace-nowrap">
            <thead class="text-xs tracking-wide text-stone-500 uppercase">
              <tr>
                <th class="py-1.5 font-semibold">
                  Categoria
                </th>
                <th class="py-1.5 text-right font-semibold">
                  Gasto
                </th>
                <th class="py-1.5 text-right font-semibold">
                  Consumo
                </th>
                <th class="py-1.5 text-right font-semibold">
                  Perdas
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-stone-100">
              <tr
                v-for="categoria in porCategoria"
                :key="categoria.categoria_id ?? 'sem'"
                data-teste="categoria"
              >
                <td class="py-2 font-medium text-stone-800">
                  {{ categoria.categoria ?? 'Sem categoria' }}
                </td>
                <td class="py-2 text-right tabular-nums">
                  {{ reais(categoria.gasto) }}
                </td>
                <td class="py-2 text-right tabular-nums">
                  {{ reais(categoria.consumo) }}
                </td>
                <td class="py-2 text-right tabular-nums">
                  {{ reais(categoria.perdas) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <h2 class="mt-6 text-base font-semibold text-stone-900">
          Por fornecedor
        </h2>
        <p
          v-if="!porFornecedor.length"
          class="mt-2 text-sm text-stone-500"
        >
          Nenhuma compra no período.
        </p>
        <table
          v-else
          class="mt-2 w-full text-left text-sm"
        >
          <tbody class="divide-y divide-stone-100">
            <tr
              v-for="fornecedor in porFornecedor"
              :key="fornecedor.fornecedor_id ?? 'sem'"
              data-teste="por-fornecedor"
            >
              <td class="py-2 font-medium text-stone-800">
                {{ fornecedor.fornecedor ?? 'Sem fornecedor' }}
                <span class="block text-xs font-normal text-stone-500">
                  {{ plural(fornecedor.compras, 'compra', 'compras') }}<template v-if="fornecedor.compras_sem_preco">
                    , {{ fornecedor.compras_sem_preco }} sem preço
                  </template>
                </span>
              </td>
              <td class="py-2 text-right font-semibold tabular-nums">
                {{ reais(fornecedor.gasto) }}
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>

    <section
      v-if="relatorio.limitacoes.length"
      class="mt-6 text-sm text-stone-500"
      data-teste="limitacoes"
    >
      <h2 class="font-semibold text-stone-700">
        O que a conta não sabe
      </h2>
      <ul class="mt-1 list-disc pl-5">
        <li
          v-for="texto in relatorio.limitacoes"
          :key="texto"
        >
          {{ texto }}
        </li>
      </ul>
    </section>
  </template>
</template>
