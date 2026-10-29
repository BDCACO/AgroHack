<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, useTemplateRef } from 'vue'

import { reais } from '@/formatos'
import * as api from '@/services/compras'
import { mensagemDeErro, useEstoqueStore } from '@/stores/estoque'
import { useFornecedoresStore } from '@/stores/fornecedores'
import type { Pedido, PedidoEntrada } from '@/types/api'

/** O pedido novo (vazio ou vindo da sugestão) ou a alteração de um aberto. */
const props = defineProps<{
  pedido?: Pedido
  rascunho?: Pick<PedidoEntrada, 'fornecedor_id' | 'itens'>
}>()
const emit = defineEmits<{ salvo: [pedido: Pedido]; cancelar: [] }>()

const estoque = useEstoqueStore()
const fornecedores = useFornecedoresStore()
const hoje = () => new Date().toLocaleDateString('sv-SE')

interface Linha {
  insumoId: number | ''
  quantidade: number | ''
  preco: number | ''
}
const linhaVazia = (): Linha => ({ insumoId: '', quantidade: '', preco: '' })
const origem = props.pedido ?? props.rascunho
const form = reactive({
  fornecedorId: (origem?.fornecedor_id ?? '') as number | '',
  feitoEm: props.pedido?.feito_em ?? hoje(),
  previstoPara: props.pedido?.previsto_para ?? '',
  observacao: props.pedido?.observacao ?? '',
  linhas: origem?.itens.length
    ? origem.itens.map((item): Linha => ({
        insumoId: item.insumo_id,
        quantidade: item.quantidade,
        preco: item.valor_unitario ?? '',
      }))
    : [linhaVazia()],
})
const salvando = ref(false)
const erro = ref<string | null>(null)
const titulo = useTemplateRef<HTMLElement>('titulo')
onMounted(() => nextTick(() => titulo.value?.focus()))

// Na alteração, o fornecedor desativado do pedido continua na lista, para não sumir.
const escolhas = computed(() =>
  fornecedores.fornecedores.filter((f) => f.ativo || f.id === props.pedido?.fornecedor_id),
)
const unidade = (linha: Linha) =>
  linha.insumoId === '' ? '' : (estoque.insumoPorId.get(linha.insumoId)?.unidade ?? '')
const estimado = computed(() => {
  const comPreco = form.linhas.filter((l) => l.quantidade !== '' && l.preco !== '')
  return comPreco.length
    ? comPreco.reduce((soma, l) => soma + Number(l.quantidade) * Number(l.preco), 0)
    : null
})

async function salvar() {
  const linhas = form.linhas.filter((l) => l.insumoId !== '' && l.quantidade !== '')
  if (!linhas.length) {
    erro.value = 'Escolha pelo menos um insumo, com a quantidade.'
    return
  }
  salvando.value = true
  erro.value = null
  const dados: PedidoEntrada = {
    fornecedor_id: form.fornecedorId === '' ? null : form.fornecedorId,
    feito_em: form.feitoEm,
    previsto_para: form.previstoPara || null,
    observacao: form.observacao || null,
    itens: linhas.map((l) => ({
      insumo_id: Number(l.insumoId),
      quantidade: Number(l.quantidade),
      valor_unitario: l.preco === '' ? null : Number(l.preco),
    })),
  }
  try {
    const salvo = props.pedido
      ? await api.atualizarPedido(props.pedido.id, dados)
      : await api.criarPedido(dados)
    emit('salvo', salvo)
  } catch (falha) {
    erro.value = mensagemDeErro(falha)
  } finally {
    salvando.value = false
  }
}
</script>

<template>
  <form
    class="cartao mt-2 mb-6 grid animate-surgir gap-4 p-5"
    data-teste="formulario-pedido"
    @submit.prevent="salvar"
  >
    <h2
      ref="titulo"
      tabindex="-1"
      class="text-base font-semibold text-stone-900 focus:outline-none"
    >
      {{ pedido ? `Alterar o pedido nº ${pedido.id}` : 'Novo pedido de compra' }}
    </h2>
    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <label class="flutuante">
        <select
          v-model="form.fornecedorId"
          class="campo"
          data-teste="fornecedor"
        >
          <option value="">
            Sem fornecedor cadastrado
          </option>
          <option
            v-for="fornecedor in escolhas"
            :key="fornecedor.id"
            :value="fornecedor.id"
          >
            {{ fornecedor.nome }}
          </option>
        </select>
        <span class="rotulo">Fornecedor</span>
      </label>
      <label class="flutuante">
        <input
          v-model="form.feitoEm"
          type="date"
          required
          :max="hoje()"
          class="campo"
        >
        <span class="rotulo">Pedido em</span>
      </label>
      <label class="flutuante">
        <input
          v-model="form.previstoPara"
          type="date"
          :min="form.feitoEm"
          class="campo"
          data-teste="previsao"
        >
        <span class="rotulo">Chega em <span class="font-normal text-stone-500">(previsão)</span></span>
      </label>
      <label class="flutuante">
        <input
          v-model="form.observacao"
          maxlength="500"
          placeholder="Frete por conta da revenda"
          class="campo"
        >
        <span class="rotulo">Observação <span class="font-normal text-stone-500">(opcional)</span></span>
      </label>
    </div>

    <fieldset class="grid gap-3">
      <legend class="mb-1 text-sm font-medium text-stone-700">
        Itens
      </legend>
      <div
        v-for="(linha, indice) in form.linhas"
        :key="indice"
        class="grid items-center gap-3 rounded-lg bg-stone-50 p-3 sm:grid-cols-[2fr_1fr_1fr_auto]"
        data-teste="linha-pedido"
      >
        <label class="flutuante">
          <select
            v-model="linha.insumoId"
            class="campo"
          >
            <option value="">
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
            v-model.number="linha.quantidade"
            type="number"
            min="0.001"
            step="any"
            placeholder=" "
            class="campo"
          >
          <span class="rotulo">Quantidade{{ unidade(linha) ? ` (${unidade(linha)})` : '' }}</span>
        </label>
        <label class="flutuante">
          <input
            v-model.number="linha.preco"
            type="number"
            min="0.0001"
            step="any"
            inputmode="decimal"
            placeholder=" "
            class="campo"
          >
          <span class="rotulo">Preço{{ unidade(linha) ? ` (R$/${unidade(linha)})` : '' }}</span>
        </label>
        <button
          type="button"
          class="botao-perigo px-3"
          :disabled="form.linhas.length === 1"
          :aria-label="`Tirar o item ${indice + 1}`"
          @click="form.linhas.splice(indice, 1)"
        >
          Tirar
        </button>
      </div>
      <div>
        <button
          type="button"
          class="botao-texto"
          @click="form.linhas.push(linhaVazia())"
        >
          + Outro insumo
        </button>
      </div>
    </fieldset>

    <p
      v-if="estimado !== null"
      class="text-sm text-stone-600"
      data-teste="estimado"
    >
      Estimado: <strong class="text-stone-900 tabular-nums">{{ reais(estimado) }}</strong>
      (dos itens com preço)
    </p>
    <p
      v-if="erro"
      role="alert"
      class="text-sm text-red-700"
    >
      {{ erro }}
    </p>
    <div class="flex gap-2">
      <button
        type="submit"
        class="botao-primario"
        :disabled="salvando"
      >
        {{ salvando ? 'Salvando…' : pedido ? 'Salvar pedido' : 'Fazer pedido' }}
      </button>
      <button
        type="button"
        class="botao-texto text-stone-700 hover:bg-stone-100"
        @click="emit('cancelar')"
      >
        Cancelar
      </button>
    </div>
  </form>
</template>
