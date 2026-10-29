<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
import FormularioDePedido from '@/components/FormularioDePedido.vue'
import IconeSvg from '@/components/IconeSvg.vue'
import JanelaModal from '@/components/JanelaModal.vue'
import ReceberPedido from '@/components/ReceberPedido.vue'
import { dataBr, reais } from '@/formatos'
import * as api from '@/services/compras'
import { mensagemDeErro, useEstoqueStore } from '@/stores/estoque'
import { useFornecedoresStore } from '@/stores/fornecedores'
import { useSessaoStore } from '@/stores/sessao'
import type {
  GrupoSugerido,
  Pedido,
  PedidoEntrada,
  ResultadoDoRecebimento,
  SituacaoDoPedido,
  SugestaoDePedido,
} from '@/types/api'

const estoque = useEstoqueStore()
const fornecedores = useFornecedoresStore()
const sessao = useSessaoStore()

const pedidos = ref<Pedido[]>([])
const carregado = ref(false)
const erro = ref<string | null>(null)
// A sugestão é de quem compra: o funcionário vê os pedidos e recebe a carga.
const sugestao = ref<SugestaoDePedido | null>(null)

async function carregarPedidos() {
  erro.value = null
  try {
    pedidos.value = await api.listarPedidos()
    carregado.value = true
  } catch (falha) {
    erro.value = mensagemDeErro(falha)
  }
}
async function carregarSugestao() {
  if (!sessao.podeGerir) return
  try {
    sugestao.value = await api.sugerirPedido()
  } catch {
    // Sem a sugestão, a tela segue com os pedidos.
    sugestao.value = null
  }
}
onMounted(() => Promise.all([carregarPedidos(), carregarSugestao(), fornecedores.carregar()]))

/** Pedido feito, recebido ou cancelado muda o estoque, o "a caminho" e a sugestão. */
async function recarregarTudo() {
  await Promise.all([carregarPedidos(), carregarSugestao(), estoque.carregar()])
}

type Filtro = 'caminho' | 'recebido' | 'cancelado' | 'todos'
const filtro = ref<Filtro>('caminho')
const filtros: { valor: Filtro; rotulo: string; situacoes: SituacaoDoPedido[] }[] = [
  { valor: 'caminho', rotulo: 'A caminho', situacoes: ['aberto', 'parcial'] },
  { valor: 'recebido', rotulo: 'Recebidos', situacoes: ['recebido'] },
  { valor: 'cancelado', rotulo: 'Cancelados', situacoes: ['cancelado'] },
  { valor: 'todos', rotulo: 'Todos', situacoes: ['aberto', 'parcial', 'recebido', 'cancelado'] },
]
const contagem = (valor: Filtro) =>
  pedidos.value.filter((p) => filtros.find((f) => f.valor === valor)!.situacoes.includes(p.situacao)).length
const visiveis = computed(() => {
  const situacoes = filtros.find((f) => f.valor === filtro.value)!.situacoes
  return pedidos.value.filter((pedido) => situacoes.includes(pedido.situacao))
})

const rotuloDaSituacao: Record<SituacaoDoPedido, { texto: string; cor: string }> = {
  aberto: { texto: 'A caminho', cor: 'bg-sky-50 text-sky-800 ring-sky-600/20' },
  parcial: { texto: 'Chegou parte', cor: 'bg-amber-50 text-amber-800 ring-amber-500/30' },
  recebido: { texto: 'Recebido', cor: 'bg-campo-50 text-campo-700 ring-campo-600/20' },
  cancelado: { texto: 'Cancelado', cor: 'bg-stone-100 text-stone-600 ring-stone-400/30' },
}
const numero = (valor: number) => valor.toLocaleString('pt-BR', { maximumFractionDigits: 3 })

// O formulário: pedido novo, vindo da sugestão, ou alteração de um aberto.
const formulario = ref<{ pedido?: Pedido; rascunho?: Pick<PedidoEntrada, 'fornecedor_id' | 'itens'> } | null>(null)
const aviso = ref<string | null>(null)

function pedirDaSugestao(grupo: GrupoSugerido) {
  formulario.value = {
    rascunho: {
      fornecedor_id: grupo.fornecedor_id,
      itens: grupo.itens.map((item) => ({
        insumo_id: item.insumo_id,
        quantidade: item.quantidade,
        valor_unitario: item.valor_unitario,
      })),
    },
  }
  aviso.value = null
}
async function aoSalvar(pedido: Pedido) {
  const novo = !formulario.value?.pedido
  formulario.value = null
  aviso.value = novo
    ? `Pedido nº ${pedido.id} feito. Enquanto não chega, a reposição já desconta o que vem.`
    : `Pedido nº ${pedido.id} alterado.`
  filtro.value = 'caminho'
  await recarregarTudo()
}

// Só o pedido aberto, antes de chegar qualquer coisa, se altera.
const podeAlterar = (pedido: Pedido) =>
  sessao.podeGerir && pedido.situacao === 'aberto' && pedido.itens.every((i) => i.quantidade_recebida === 0)
const podeReceber = (pedido: Pedido) => pedido.situacao === 'aberto' || pedido.situacao === 'parcial'

const emRecebimento = ref<Pedido | null>(null)
const avisosDoRecebimento = ref<string[]>([])
async function aoReceber(resultado: ResultadoDoRecebimento) {
  emRecebimento.value = null
  const entradas = resultado.movimentacoes.length
  aviso.value = `Pedido nº ${resultado.pedido.id}: ${entradas === 1 ? '1 entrada lançada' : `${entradas} entradas lançadas`} no estoque.`
  avisosDoRecebimento.value = resultado.avisos
  await recarregarTudo()
}

const emCancelamento = ref<Pedido | null>(null)
const cancelando = ref(false)
const erroDoCancelamento = ref<string | null>(null)
async function cancelar() {
  if (!emCancelamento.value) return
  cancelando.value = true
  erroDoCancelamento.value = null
  try {
    const cancelado = await api.cancelarPedido(emCancelamento.value.id)
    emCancelamento.value = null
    aviso.value = `Pedido nº ${cancelado.id} cancelado.`
    await recarregarTudo()
  } catch (falha) {
    erroDoCancelamento.value = mensagemDeErro(falha)
  } finally {
    cancelando.value = false
  }
}
</script>

<template>
  <CabecalhoDePagina
    titulo="Compras"
  >
    <template #acoes>
      <RouterLink
        :to="{ name: 'fornecedores' }"
        class="botao-secundario"
      >
        <IconeSvg
          nome="loja"
          class="h-4 w-4"
        />
        Fornecedores
      </RouterLink>
      <button
        v-if="sessao.podeGerir && !formulario"
        type="button"
        class="botao-primario"
        @click="formulario = {}; aviso = null"
      >
        Novo pedido
      </button>
    </template>
  </CabecalhoDePagina>

  <FormularioDePedido
    v-if="formulario"
    :key="formulario.pedido?.id ?? 'novo'"
    :pedido="formulario.pedido"
    :rascunho="formulario.rascunho"
    @salvo="aoSalvar"
    @cancelar="formulario = null"
  />

  <div
    v-if="aviso"
    role="status"
    class="mb-4 rounded-lg bg-campo-50 px-4 py-3 text-sm text-campo-800"
    data-teste="aviso"
  >
    <p class="flex items-center gap-1.5">
      <IconeSvg
        nome="confirmado"
        class="h-4 w-4 shrink-0"
      />
      {{ aviso }}
    </p>
    <ul
      v-if="avisosDoRecebimento.length"
      class="mt-2 list-disc pl-6 text-amber-800"
      data-teste="avisos-recebimento"
    >
      <li
        v-for="texto in avisosDoRecebimento"
        :key="texto"
      >
        {{ texto }}
      </li>
    </ul>
  </div>

  <!-- A sugestão: o que a reposição pede para os próximos dias, já por revenda. -->
  <section
    v-if="sugestao && !formulario"
    class="mb-6 animate-surgir"
    data-teste="sugestao"
  >
    <h2 class="text-base font-semibold text-stone-900">
      Sugestão de compra
    </h2>
    <p class="text-sm text-stone-600">
      {{ sugestao.grupos.length
        ? `O que pedir hoje ou nos próximos ${sugestao.dias} dias, separado pela revenda da última compra, com o que já está a caminho descontado.`
        : `Nada a pedir nos próximos ${sugestao.dias} dias: o estoque, com o que já está a caminho, cobre o consumo.` }}
    </p>
    <div class="mt-3 grid gap-3 lg:grid-cols-2">
      <article
        v-for="grupo in sugestao.grupos"
        :key="grupo.fornecedor_id ?? 'sem'"
        class="cartao flex flex-col p-4"
        data-teste="grupo-sugerido"
      >
        <div class="flex items-start justify-between gap-3">
          <div>
            <h3 class="font-semibold text-stone-900">
              {{ grupo.fornecedor ?? 'Sem fornecedor' }}
            </h3>
            <p
              v-if="grupo.custo_estimado !== null"
              class="text-sm text-stone-500"
            >
              Cerca de <span class="font-semibold text-stone-800 tabular-nums">{{ reais(grupo.custo_estimado) }}</span>
            </p>
          </div>
          <button
            type="button"
            class="botao-primario shrink-0"
            @click="pedirDaSugestao(grupo)"
          >
            Fazer este pedido
          </button>
        </div>
        <ul class="mt-3 divide-y divide-stone-100 text-sm">
          <li
            v-for="item in grupo.itens"
            :key="item.insumo_id"
            class="py-2"
          >
            <div class="flex items-baseline justify-between gap-3">
              <span class="font-medium text-stone-800">{{ item.insumo }}</span>
              <span class="font-semibold whitespace-nowrap tabular-nums">{{ numero(item.quantidade) }} {{ item.unidade }}</span>
            </div>
            <p class="flex flex-wrap items-center gap-x-2 text-xs text-stone-500">
              <span
                v-if="item.pedir_hoje"
                class="font-semibold text-red-700"
              >Pedir hoje</span>
              <span v-else>Pedir até {{ dataBr(item.pedir_em) }}</span>
              <span v-if="item.valor_unitario !== null">· {{ reais(item.valor_unitario) }}/{{ item.unidade }}</span>
            </p>
          </li>
        </ul>
      </article>
    </div>
    <details
      v-if="sugestao.limitacoes.length"
      class="mt-2 text-sm text-stone-500"
    >
      <summary class="cursor-pointer">
        O que a sugestão não sabe ({{ sugestao.limitacoes.length }})
      </summary>
      <ul class="mt-1 list-disc pl-5">
        <li
          v-for="texto in sugestao.limitacoes"
          :key="texto"
        >
          {{ texto }}
        </li>
      </ul>
    </details>
  </section>

  <h2 class="text-base font-semibold text-stone-900">
    Pedidos
  </h2>
  <div
    class="mt-2 mb-3 flex flex-wrap gap-1"
    role="group"
    aria-label="Filtrar pedidos"
  >
    <button
      v-for="opcao in filtros"
      :key="opcao.valor"
      type="button"
      class="rounded-full px-3 py-1.5 text-sm font-medium transition-colors pointer-coarse:min-h-11"
      :class="filtro === opcao.valor ? 'bg-campo-600 text-white' : 'bg-white text-stone-700 ring-1 ring-stone-200 hover:bg-stone-50'"
      :aria-pressed="filtro === opcao.valor"
      @click="filtro = opcao.valor"
    >
      {{ opcao.rotulo }} <span class="tabular-nums opacity-75">{{ contagem(opcao.valor) }}</span>
    </button>
  </div>

  <p
    v-if="erro"
    role="alert"
    class="text-sm text-red-700"
  >
    {{ erro }}
  </p>

  <EstadoVazio
    v-else-if="carregado && !pedidos.length"
    icone="caminhao"
    titulo="Nenhum pedido de compra"
    :texto="sessao.podeGerir
      ? 'Faça o pedido pela sugestão acima ou em Novo pedido. Enquanto ele não chega, a reposição desconta o que vem; quando chega, o recebimento lança a entrada no estoque.'
      : 'Quando o dono fizer um pedido, ele aparece aqui. Na chegada da carga, é aqui que se confere e lança no estoque.'"
  />

  <p
    v-else-if="carregado && !visiveis.length"
    class="text-sm text-stone-500"
  >
    Nenhum pedido aqui.
  </p>

  <ul
    v-else
    class="grid animate-surgir gap-3"
  >
    <li
      v-for="pedido in visiveis"
      :key="pedido.id"
      class="cartao p-4"
      :class="pedido.atrasado ? 'border-amber-300' : ''"
      data-teste="pedido"
    >
      <div class="flex flex-wrap items-start gap-x-3 gap-y-2">
        <div class="min-w-0 flex-1">
          <h3 class="font-semibold text-stone-900">
            Pedido nº {{ pedido.id }} · {{ pedido.fornecedor ?? 'Sem fornecedor' }}
          </h3>
          <p class="text-sm text-stone-500">
            Feito em {{ dataBr(pedido.feito_em) }}<template v-if="pedido.feito_por">
              por {{ pedido.feito_por }}
            </template><template v-if="pedido.previsto_para">
              · chega em {{ dataBr(pedido.previsto_para) }}
            </template>
          </p>
        </div>
        <span
          v-if="pedido.atrasado"
          class="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-800 ring-1 ring-amber-500/30 ring-inset"
          data-teste="atrasado"
        >Atrasado</span>
        <span
          class="rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset"
          :class="rotuloDaSituacao[pedido.situacao].cor"
          data-teste="situacao"
        >{{ rotuloDaSituacao[pedido.situacao].texto }}</span>
      </div>

      <table class="mt-3 w-full text-left text-sm">
        <thead class="text-xs tracking-wide text-stone-500 uppercase">
          <tr>
            <th class="py-1.5 font-semibold">
              Insumo
            </th>
            <th class="py-1.5 text-right font-semibold">
              Pedido
            </th>
            <th class="py-1.5 text-right font-semibold">
              Chegou
            </th>
            <th class="hidden py-1.5 text-right font-semibold sm:table-cell">
              Preço
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-stone-100">
          <tr
            v-for="item in pedido.itens"
            :key="item.id"
          >
            <td class="py-1.5 font-medium text-stone-800">
              {{ item.insumo }}
            </td>
            <td class="py-1.5 text-right whitespace-nowrap tabular-nums">
              {{ numero(item.quantidade) }} {{ item.unidade }}
            </td>
            <td
              class="py-1.5 text-right whitespace-nowrap tabular-nums"
              :class="item.falta_receber > 0 && pedido.situacao !== 'cancelado' ? 'text-amber-800' : 'text-campo-700'"
            >
              {{ numero(item.quantidade_recebida) }} {{ item.unidade }}
            </td>
            <td class="hidden py-1.5 text-right whitespace-nowrap text-stone-600 tabular-nums sm:table-cell">
              {{ item.valor_unitario === null ? '—' : `${reais(item.valor_unitario)}/${item.unidade}` }}
            </td>
          </tr>
        </tbody>
      </table>

      <p
        v-if="pedido.observacao"
        class="mt-2 text-sm text-stone-600"
      >
        {{ pedido.observacao }}
      </p>

      <div class="mt-3 flex flex-wrap items-center gap-2 border-t border-stone-100 pt-3">
        <p
          v-if="pedido.custo_estimado !== null"
          class="mr-auto text-sm text-stone-600"
        >
          Estimado <span class="font-semibold text-stone-900 tabular-nums">{{ reais(pedido.custo_estimado) }}</span>
        </p>
        <span
          v-else
          class="mr-auto"
        />
        <button
          v-if="podeAlterar(pedido)"
          type="button"
          class="botao-texto"
          :aria-label="`Alterar o pedido nº ${pedido.id}`"
          @click="formulario = { pedido }; aviso = null"
        >
          Alterar
        </button>
        <button
          v-if="sessao.podeGerir && podeReceber(pedido)"
          type="button"
          class="botao-perigo"
          :aria-label="`Cancelar o pedido nº ${pedido.id}`"
          @click="emCancelamento = pedido; erroDoCancelamento = null"
        >
          Cancelar
        </button>
        <button
          v-if="podeReceber(pedido)"
          type="button"
          class="botao-primario"
          :aria-label="`Receber o pedido nº ${pedido.id}`"
          @click="emRecebimento = pedido; avisosDoRecebimento = []"
        >
          <IconeSvg
            nome="caminhao"
            class="h-4 w-4"
          />
          Receber
        </button>
      </div>
    </li>
  </ul>

  <ReceberPedido
    v-if="emRecebimento"
    :pedido="emRecebimento"
    @fechar="emRecebimento = null"
    @recebido="aoReceber"
  />

  <JanelaModal
    v-if="emCancelamento"
    titulo="Cancelar pedido"
    @fechar="emCancelamento = null"
  >
    <p class="text-sm text-stone-600">
      Cancelar o pedido nº {{ emCancelamento.id }}? O que falta chegar não vem mais e sai da conta
      da reposição. O que já chegou continua no estoque.
    </p>
    <p
      v-if="erroDoCancelamento"
      role="alert"
      class="mt-3 text-sm text-red-700"
    >
      {{ erroDoCancelamento }}
    </p>
    <div class="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <button
        type="button"
        class="botao-secundario"
        autofocus
        @click="emCancelamento = null"
      >
        Voltar
      </button>
      <button
        type="button"
        class="botao-perigo border border-red-700/30"
        :disabled="cancelando"
        data-teste="confirmar-cancelamento"
        @click="cancelar"
      >
        Cancelar pedido
      </button>
    </div>
  </JanelaModal>
</template>
