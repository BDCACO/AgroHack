<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import IconeSvg from '@/components/IconeSvg.vue'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import ConfirmarRemocao from '@/components/ConfirmarRemocao.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
import { reais } from '@/formatos'
import { mensagemDeErro, useEstoqueStore } from '@/stores/estoque'
import { useSessaoStore } from '@/stores/sessao'
import type { Movimentacao, MovimentacaoEntrada } from '@/types/api'

const estoque = useEstoqueStore()
const sessao = useSessaoStore()
onMounted(() => estoque.carregar())

// AAAA-MM-DD no fuso do navegador (o do produtor); 'sv-SE' formata exatamente assim.
const hoje = () => new Date().toLocaleDateString('sv-SE')

// Vindo da página de um insumo (?insumo=ID), o formulário já abre nele.
const insumoDaUrl = Number(useRoute().query.insumo) || ''
const form = reactive({
  tipo: 'saida' as MovimentacaoEntrada['tipo'],
  insumoId: insumoDaUrl as number | '',
  data: hoje(),
  quantidade: '' as number | '',
  validade: '',
  // R$ por unidade do insumo, o que se pagou nesta compra.
  preco: '' as number | '',
})
const salvando = ref(false)
// A linha recém-lançada acende na tabela e volta ao normal: mostra onde ela entrou.
const destacada = ref<number | null>(null)
const erroDoForm = ref<string | null>(null)
// O que acabou de ser lançado, em palavras, ao lado do botão: no celular a lista fica lá
// embaixo, fora da tela, e é aqui que se vê que deu certo.
const confirmacao = ref<string | null>(null)

// Validade é de lote, e lote só chega numa entrada; preço é o da compra, também só nela.
watch(
  () => form.tipo,
  (tipo) => {
    if (tipo === 'saida') {
      form.validade = ''
      form.preco = ''
    }
  },
)
const unidadeEscolhida = computed(() =>
  form.insumoId === '' ? undefined : estoque.insumoPorId.get(form.insumoId)?.unidade,
)

async function lancar() {
  if (form.insumoId === '' || form.quantidade === '') return
  salvando.value = true
  erroDoForm.value = null
  confirmacao.value = null
  try {
    const criada = await estoque.registrarMovimentacao({
      insumo_id: form.insumoId,
      tipo: form.tipo,
      data: form.data,
      quantidade: form.quantidade,
      validade: form.validade || null,
      valor_unitario: form.preco === '' ? null : form.preco,
    })
    destacada.value = criada.id
    const insumo = estoque.insumoPorId.get(criada.insumo_id)
    const preco = criada.valor_unitario ? `, a ${precoPor(criada.valor_unitario, insumo?.unidade)}` : ''
    confirmacao.value = `${rotulo[criada.tipo]} de ${numero(criada.quantidade)} ${insumo?.unidade ?? ''} de ${insumo?.nome ?? 'insumo'}${preco} lançada.`
    // No celular Android, uma vibração curta confirma sem precisar olhar.
    navigator.vibrate?.(20)
    // Mantém tipo, insumo e data: lançamentos em sequência costumam repetir os três.
    form.quantidade = ''
    form.validade = ''
    form.preco = ''
  } catch (erro) {
    erroDoForm.value = mensagemDeErro(erro)
  } finally {
    salvando.value = false
  }
}

// A que está para sair, esperando o "Remover" da janela de confirmação.
const emRemocao = ref<Movimentacao | null>(null)
function remover(movimentacao: Movimentacao) {
  emRemocao.value = movimentacao
}
function textoDaRemocao(movimentacao: Movimentacao) {
  const insumo = estoque.insumoPorId.get(movimentacao.insumo_id)
  const resumo = `${rotulo[movimentacao.tipo].toLowerCase()} de ${numero(movimentacao.quantidade)} ${insumo?.unidade ?? ''} de ${insumo?.nome ?? 'insumo'}`
  return `Remover a ${resumo} em ${dataBr(movimentacao.data)}? O estoque do insumo será recalculado.`
}

const rotulo = { entrada: 'Entrada', saida: 'Saída' } as const
const numero = (valor: number) => valor.toLocaleString('pt-BR', { maximumFractionDigits: 3 })
const dataBr = (data: string) => data.split('-').reverse().join('/')
const precoPor = (valor: number, unidade?: string) => `${reais(valor)}${unidade ? `/${unidade}` : ''}`

// No celular, a lista vem agrupada por dia, como um extrato: "Hoje", "Ontem", e depois o
// dia da semana com a data. A API já manda da mais recente para a mais antiga.
function rotuloDoDia(data: string) {
  const ontem = new Date(`${hoje()}T12:00:00`)
  ontem.setDate(ontem.getDate() - 1)
  if (data === hoje()) return 'Hoje'
  if (data === ontem.toLocaleDateString('sv-SE')) return 'Ontem'
  return new Date(`${data}T12:00:00`).toLocaleDateString('pt-BR', {
    weekday: 'long',
    day: '2-digit',
    month: '2-digit',
  })
}
const porDia = computed(() => {
  const dias: { data: string; rotulo: string; movimentacoes: Movimentacao[] }[] = []
  for (const mov of estoque.movimentacoes) {
    const dia = dias.at(-1)
    if (dia?.data === mov.data) dia.movimentacoes.push(mov)
    else dias.push({ data: mov.data, rotulo: rotuloDoDia(mov.data), movimentacoes: [mov] })
  }
  return dias
})
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
      class="botao-primario"
    >
      Ir para Insumos
    </RouterLink>
  </EstadoVazio>

  <template v-else-if="estoque.insumos.length">
    <form
      class="cartao mt-2 grid animate-surgir items-end gap-4 p-5 sm:grid-cols-2 lg:grid-cols-6"
      @submit.prevent="lancar"
    >
      <fieldset class="sm:col-span-2 lg:col-span-6">
        <legend class="text-sm font-medium text-stone-700">
          Tipo
        </legend>
        <!-- O fundo verde desliza para a opção escolhida: a troca fica visível. -->
        <div class="relative mt-1.5 grid grid-cols-2 rounded-lg bg-stone-100 p-1 sm:inline-grid">
          <span
            class="absolute inset-y-1 left-1 w-[calc(50%-0.25rem)] rounded-md bg-campo-600 shadow-sm transition-transform duration-250 ease-movimento"
            :class="form.tipo === 'entrada' ? 'translate-x-full' : 'translate-x-0'"
            aria-hidden="true"
          />
          <label
            v-for="tipo in (['saida', 'entrada'] as const)"
            :key="tipo"
            class="relative z-10 cursor-pointer rounded-md px-2 py-1.5 text-center text-sm font-semibold sm:px-4 pointer-coarse:py-2.5 transition-colors duration-250 ease-movimento has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-campo-600 has-[:focus-visible]:ring-offset-1"
            :class="form.tipo === tipo ? 'text-white' : 'text-stone-600 hover:text-stone-900'"
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
        class="text-sm font-medium text-stone-700"
      >
        Preço (R$/{{ unidadeEscolhida ?? 'un.' }}) <span class="font-normal text-stone-500">(se souber)</span>
        <input
          v-model.number="form.preco"
          type="number"
          min="0.0001"
          step="any"
          inputmode="decimal"
          class="campo"
          data-teste="preco"
        >
      </label>
      <label
        v-if="form.tipo === 'entrada'"
        class="text-sm font-medium text-stone-700"
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
      <div class="flex flex-wrap items-center gap-x-4 gap-y-3 sm:col-span-2 lg:col-span-6">
        <button
          type="submit"
          class="botao-primario max-sm:w-full"
          :disabled="salvando"
        >
          {{ salvando ? 'Lançando…' : 'Lançar' }}
        </button>
        <p
          class="flex items-center gap-1.5 text-sm text-campo-700"
          role="status"
          data-teste="confirmacao"
        >
          <template v-if="confirmacao">
            <IconeSvg
              nome="confirmado"
              class="h-4 w-4 shrink-0"
            />
            {{ confirmacao }}
          </template>
        </p>
      </div>
    </form>

    <p
      v-if="!estoque.movimentacoes.length"
      class="mt-6 text-sm text-stone-500"
    >
      Nenhuma movimentação lançada ainda. Comece pelo estoque que já está no galpão: lance como
      entrada, com a data de hoje.
    </p>
    <template v-else>
      <!-- No celular, um extrato por dia no lugar da tabela, que não cabe sem rolar para o
           lado. O dia fica preso no alto enquanto se rola por ele. -->
      <div class="mt-6 animate-surgir space-y-5 [animation-delay:80ms] md:hidden">
        <section
          v-for="dia in porDia"
          :key="dia.data"
          :aria-label="dia.rotulo"
        >
          <h2
            class="sticky top-0 z-10 -mx-4 bg-stone-50/95 px-4 py-2 sm:-mx-6 sm:px-6 text-xs font-semibold tracking-wide text-stone-500 uppercase backdrop-blur-sm"
            data-teste="dia"
          >
            {{ dia.rotulo }}
          </h2>
          <ul class="cartao mt-1 divide-y divide-stone-100">
            <li
              v-for="mov in dia.movimentacoes"
              :key="mov.id"
              class="flex items-center gap-3 py-2.5 pr-1 pl-3"
              :class="mov.id === destacada ? 'animate-destaque' : ''"
              data-teste="movimentacao-celular"
            >
              <!-- Entrada aponta para o galpão (desce), saída para fora (sobe). -->
              <span
                class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
                :class="mov.tipo === 'entrada' ? 'bg-campo-50 text-campo-700' : 'bg-terra-50 text-terra-700'"
                aria-hidden="true"
              >
                <IconeSvg
                  nome="seta"
                  class="h-5 w-5"
                  :class="mov.tipo === 'entrada' ? 'rotate-90' : '-rotate-90'"
                />
              </span>
              <div class="min-w-0 flex-1">
                <RouterLink
                  :to="{ name: 'insumo', params: { id: mov.insumo_id } }"
                  class="block text-sm leading-snug font-semibold text-stone-800"
                >
                  {{ estoque.insumoPorId.get(mov.insumo_id)?.nome }}
                </RouterLink>
                <p class="text-xs text-stone-500">
                  {{ rotulo[mov.tipo] }}<template v-if="mov.valor_unitario">
                    · {{ precoPor(mov.valor_unitario, estoque.insumoPorId.get(mov.insumo_id)?.unidade) }}
                  </template><template v-if="mov.validade">
                    · validade {{ dataBr(mov.validade) }}
                  </template><template v-if="mov.lancado_por">
                    · por {{ mov.lancado_por }}
                  </template>
                </p>
              </div>
              <p
                class="text-right text-sm font-semibold whitespace-nowrap tabular-nums"
                :class="mov.tipo === 'entrada' ? 'text-campo-700' : 'text-stone-800'"
              >
                {{ mov.tipo === 'entrada' ? '+' : '−' }}{{ numero(mov.quantidade) }}
                {{ estoque.insumoPorId.get(mov.insumo_id)?.unidade }}
              </p>
              <button
                v-if="sessao.podeGerir"
                type="button"
                class="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-stone-400 transition-colors active:bg-red-50 active:text-red-700"
                :aria-label="`Remover ${rotulo[mov.tipo].toLowerCase()} de ${estoque.insumoPorId.get(mov.insumo_id)?.nome ?? 'insumo'}, ${dia.rotulo.toLowerCase()}`"
                @click="remover(mov)"
              >
                <IconeSvg
                  nome="lixeira"
                  class="h-5 w-5"
                />
              </button>
            </li>
          </ul>
        </section>
      </div>

      <div class="cartao mt-6 hidden animate-surgir overflow-x-auto [animation-delay:80ms] md:block">
        <table class="w-full text-left text-sm">
          <caption class="sr-only">
            Últimas movimentações
          </caption>
          <thead class="bg-stone-50/80 text-xs tracking-wide text-stone-500 uppercase">
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
              <th class="px-4 py-3 text-right font-semibold">
                Preço
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
              class="transition-colors hover:bg-stone-50/70"
              :class="mov.id === destacada ? 'animate-destaque' : ''"
            >
              <td class="px-4 py-3 tabular-nums">
                {{ dataBr(mov.data) }}
              </td>
              <td class="px-4 py-3 font-medium text-stone-800">
                <RouterLink
                  :to="{ name: 'insumo', params: { id: mov.insumo_id } }"
                  class="hover:text-campo-700 hover:underline"
                >
                  {{ estoque.insumoPorId.get(mov.insumo_id)?.nome }}
                </RouterLink>
                <span
                  v-if="mov.lancado_por"
                  class="block text-xs font-normal text-stone-500"
                >por {{ mov.lancado_por }}</span>
              </td>
              <td class="px-4 py-3">
                <!-- Entrada aponta para o galpão (desce), saída para fora (sobe). -->
                <span
                  class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset"
                  :class="mov.tipo === 'entrada' ? 'bg-campo-50 text-campo-700 ring-campo-600/20' : 'bg-terra-50 text-terra-700 ring-terra-500/25'"
                >
                  <IconeSvg
                    nome="seta"
                    class="h-3.5 w-3.5"
                    :class="mov.tipo === 'entrada' ? 'rotate-90' : '-rotate-90'"
                  />
                  {{ rotulo[mov.tipo] }}
                </span>
              </td>
              <td class="px-4 py-3 text-right tabular-nums">
                {{ numero(mov.quantidade) }} {{ estoque.insumoPorId.get(mov.insumo_id)?.unidade }}
              </td>
              <td class="px-4 py-3 text-right tabular-nums text-stone-600">
                {{ mov.valor_unitario ? precoPor(mov.valor_unitario, estoque.insumoPorId.get(mov.insumo_id)?.unidade) : '—' }}
              </td>
              <td class="px-4 py-3 tabular-nums text-stone-600">
                {{ mov.validade ? dataBr(mov.validade) : '—' }}
              </td>
              <td class="px-4 py-3 text-right">
                <button
                  v-if="sessao.podeGerir"
                  type="button"
                  class="rounded-md px-2 py-1 text-sm font-medium text-red-700 transition-colors hover:bg-red-50"
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

  <ConfirmarRemocao
    v-if="emRemocao"
    titulo="Remover movimentação"
    :texto="textoDaRemocao(emRemocao)"
    :remover="() => estoque.removerMovimentacao(emRemocao!.id)"
    @fechar="emRemocao = null"
  />
</template>
