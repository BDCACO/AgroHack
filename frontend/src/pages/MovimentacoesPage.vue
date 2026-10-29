<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import IconeSvg from '@/components/IconeSvg.vue'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import ConfirmarRemocao from '@/components/ConfirmarRemocao.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
import { reais } from '@/formatos'
import { buscarMovimentacoes } from '@/services/estoque'
import { mensagemDeErro, useEstoqueStore } from '@/stores/estoque'
import { useFornecedoresStore } from '@/stores/fornecedores'
import { useSessaoStore } from '@/stores/sessao'
import { useTalhoesStore } from '@/stores/talhoes'
import type { FiltroDeMovimentacoes, Movimentacao, MovimentacaoEntrada } from '@/types/api'

const estoque = useEstoqueStore()
const sessao = useSessaoStore()
const talhoes = useTalhoesStore()
const fornecedores = useFornecedoresStore()
onMounted(() => Promise.all([estoque.carregar(), talhoes.carregar(), fornecedores.carregar()]))

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
  // Onde a retirada foi aplicada: dá a carência e o custo por talhão.
  talhaoId: '' as number | '',
  // De quem se comprou: guarda o preço pago a cada revenda e separa a sugestão de pedido.
  fornecedorId: '' as number | '',
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
      form.fornecedorId = ''
    } else {
      form.talhaoId = ''
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
      talhao_id: form.talhaoId === '' ? null : form.talhaoId,
      fornecedor_id: form.fornecedorId === '' ? null : form.fornecedorId,
    })
    destacada.value = criada.id
    await buscar()
    const insumo = estoque.insumoPorId.get(criada.insumo_id)
    const preco = criada.valor_unitario ? `, a ${precoPor(criada.valor_unitario, insumo?.unidade)}` : ''
    const talhao = criada.talhao_id ? ` no ${nomeDoTalhao(criada.talhao_id)}` : ''
    confirmacao.value = `${rotulo[criada.tipo]} de ${numero(criada.quantidade)} ${insumo?.unidade ?? ''} de ${insumo?.nome ?? 'insumo'}${preco}${talhao} lançada.`
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

// Sem filtro, a lista é a das últimas que o estoque já carregou. Com filtro, a API busca
// uma página por vez e diz quantas há ao todo (X-Total-Count).
const POR_PAGINA = 50
const filtro = reactive<Required<FiltroDeMovimentacoes>>({ busca: '', tipo: '', desde: '', ate: '' })
const filtrando = computed(() => Object.values(filtro).some(Boolean))
const filtradas = ref<Movimentacao[]>([])
const total = ref(0)
const buscando = ref(false)
const erroDoFiltro = ref<string | null>(null)
const lista = computed(() => (filtrando.value ? filtradas.value : estoque.movimentacoes))

let pedido = 0
async function buscar(acrescentar = false) {
  if (!filtrando.value) return
  const este = ++pedido
  buscando.value = true
  erroDoFiltro.value = null
  try {
    const pagina = await buscarMovimentacoes({ ...filtro }, POR_PAGINA, acrescentar ? filtradas.value.length : 0)
    if (este !== pedido) return
    filtradas.value = acrescentar ? [...filtradas.value, ...pagina.movimentacoes] : pagina.movimentacoes
    total.value = pagina.total
  } catch (erro) {
    if (este === pedido) erroDoFiltro.value = mensagemDeErro(erro)
  } finally {
    if (este === pedido) buscando.value = false
  }
}
// A busca espera a pessoa parar de digitar; tipo e datas vão na hora.
let espera: ReturnType<typeof setTimeout> | undefined
watch(
  () => filtro.busca,
  () => {
    clearTimeout(espera)
    espera = setTimeout(() => buscar(), 300)
  },
)
watch(() => [filtro.tipo, filtro.desde, filtro.ate], () => buscar())
const limparFiltros = () => Object.assign(filtro, { busca: '', tipo: '', desde: '', ate: '' })

async function removerEAtualizar(id: number) {
  await estoque.removerMovimentacao(id)
  await buscar()
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
const nomeDoTalhao = (id: number) => talhoes.talhaoPorId.get(id)?.nome ?? 'talhão'
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
  for (const mov of lista.value) {
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
      class="cartao mt-2 grid animate-surgir items-end gap-4 p-5 sm:grid-cols-2 xl:grid-cols-6"
      @submit.prevent="lancar"
    >
      <fieldset class="sm:col-span-2 xl:col-span-6">
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
      <label class="flutuante xl:col-span-2">
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
        <span class="rotulo">Insumo</span>
      </label>
      <label class="flutuante">
        <input
          v-model="form.data"
          type="date"
          required
          :max="hoje()"
          class="campo"
        >
        <span class="rotulo">Data</span>
      </label>
      <label class="flutuante">
        <input
          v-model.number="form.quantidade"
          type="number"
          required
          min="0.001"
          step="any"
          placeholder=" "
          class="campo"
        >
        <span class="rotulo">Quantidade</span>
      </label>
      <label
        v-if="form.tipo === 'entrada'"
        class="flutuante"
      >
        <input
          v-model.number="form.preco"
          type="number"
          min="0.0001"
          step="any"
          inputmode="decimal"
          placeholder=" "
          class="campo"
          data-teste="preco"
        >
        <span class="rotulo">Preço (R$/{{ unidadeEscolhida ?? 'un.' }}) <span class="font-normal text-stone-500">(se souber)</span></span>
      </label>
      <label
        v-if="form.tipo === 'entrada'"
        class="flutuante"
      >
        <input
          v-model="form.validade"
          type="date"
          class="campo"
        >
        <span class="rotulo">Validade do lote <span class="font-normal text-stone-500">(se tiver)</span></span>
      </label>
      <label
        v-if="form.tipo === 'entrada' && fornecedores.ativos.length"
        class="flutuante xl:col-span-2"
      >
        <select
          v-model.number="form.fornecedorId"
          class="campo"
          data-teste="fornecedor"
        >
          <option value="">
            Não informar
          </option>
          <option
            v-for="fornecedor in fornecedores.ativos"
            :key="fornecedor.id"
            :value="fornecedor.id"
          >
            {{ fornecedor.nome }}
          </option>
        </select>
        <span class="rotulo">Comprado de <span class="font-normal text-stone-500">(fornecedor)</span></span>
      </label>
      <label
        v-if="form.tipo === 'saida' && talhoes.talhoes.length"
        class="flutuante xl:col-span-2"
      >
        <select
          v-model.number="form.talhaoId"
          class="campo"
          data-teste="talhao"
        >
          <option value="">
            Nenhum
          </option>
          <option
            v-for="talhao in talhoes.talhoes"
            :key="talhao.id"
            :value="talhao.id"
          >
            {{ talhao.nome }}
          </option>
        </select>
        <span class="rotulo">Aplicado no talhão <span class="font-normal text-stone-500">(se foi para a lavoura)</span></span>
      </label>
      <p
        v-if="erroDoForm"
        role="alert"
        class="text-sm text-red-700 sm:col-span-2 xl:col-span-6"
      >
        {{ erroDoForm }}
      </p>
      <div class="flex flex-wrap items-center gap-x-4 gap-y-3 sm:col-span-2 xl:col-span-6">
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
      <div
        class="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-[2fr_1fr_1fr_1fr]"
        role="search"
        aria-label="Filtrar movimentações"
      >
        <label class="flutuante">
          <input
            v-model="filtro.busca"
            type="search"
            placeholder="ureia"
            class="campo"
            data-teste="filtro-busca"
          >
          <span class="rotulo">Buscar pelo insumo</span>
        </label>
        <label class="flutuante">
          <select
            v-model="filtro.tipo"
            class="campo"
            data-teste="filtro-tipo"
          >
            <option value="">
              Entradas e saídas
            </option>
            <option value="entrada">
              Só entradas
            </option>
            <option value="saida">
              Só saídas
            </option>
          </select>
          <span class="rotulo">Tipo</span>
        </label>
        <label class="flutuante">
          <input
            v-model="filtro.desde"
            type="date"
            :max="filtro.ate || undefined"
            class="campo"
            data-teste="filtro-desde"
          >
          <span class="rotulo">De</span>
        </label>
        <label class="flutuante">
          <input
            v-model="filtro.ate"
            type="date"
            :min="filtro.desde || undefined"
            class="campo"
            data-teste="filtro-ate"
          >
          <span class="rotulo">Até</span>
        </label>
      </div>
      <p
        v-if="erroDoFiltro"
        role="alert"
        class="mt-3 text-sm text-red-700"
      >
        {{ erroDoFiltro }}
      </p>
      <p
        v-else-if="filtrando"
        class="mt-3 flex flex-wrap items-center gap-2 text-sm text-stone-600"
        role="status"
        data-teste="contagem"
      >
        <template v-if="buscando && !filtradas.length">
          Buscando…
        </template>
        <template v-else>
          {{ total === 1 ? '1 movimentação' : `${total} movimentações` }}
        </template>
        <button
          type="button"
          class="botao-texto px-2 py-0.5"
          @click="limparFiltros"
        >
          Limpar filtros
        </button>
      </p>
      <p
        v-else-if="estoque.movimentacoes.length >= 200"
        class="mt-3 text-sm text-stone-500"
      >
        Aqui estão as 200 mais recentes. Para as mais antigas, filtre pelo período.
      </p>

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
                  </template><template v-if="mov.talhao_id">
                    · {{ nomeDoTalhao(mov.talhao_id) }}
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
              v-for="mov in lista"
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
                  v-if="mov.talhao_id || mov.lancado_por"
                  class="block text-xs font-normal text-stone-500"
                >{{ [mov.talhao_id ? nomeDoTalhao(mov.talhao_id) : '', mov.lancado_por ? `por ${mov.lancado_por}` : ''].filter(Boolean).join(' · ') }}</span>
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
      <div
        v-if="filtrando && filtradas.length < total"
        class="mt-4 flex justify-center"
      >
        <button
          type="button"
          class="botao-secundario"
          :disabled="buscando"
          @click="buscar(true)"
        >
          {{ buscando ? 'Carregando…' : `Carregar mais (${total - filtradas.length})` }}
        </button>
      </div>
    </template>
  </template>

  <ConfirmarRemocao
    v-if="emRemocao"
    titulo="Remover movimentação"
    :texto="textoDaRemocao(emRemocao)"
    :remover="() => removerEAtualizar(emRemocao!.id)"
    @fechar="emRemocao = null"
  />
</template>
