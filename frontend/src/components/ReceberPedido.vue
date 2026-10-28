<script setup lang="ts">
import { reactive, ref } from 'vue'

import * as api from '@/services/compras'
import { mensagemDeErro } from '@/stores/estoque'
import type { Pedido, ResultadoDoRecebimento } from '@/types/api'

import JanelaModal from './JanelaModal.vue'

const props = defineProps<{ pedido: Pedido }>()
const emit = defineEmits<{ fechar: []; recebido: [resultado: ResultadoDoRecebimento] }>()

const hoje = () => new Date().toLocaleDateString('sv-SE')
const numero = (valor: number) => valor.toLocaleString('pt-BR', { maximumFractionDigits: 3 })

// Uma linha por item que ainda falta, já com o que falta: o comum é chegar tudo. O que não
// chegou, apaga-se a quantidade.
const form = reactive({
  data: hoje(),
  linhas: props.pedido.itens
    .filter((item) => item.falta_receber > 0)
    .map((item) => ({
      item,
      quantidade: item.falta_receber as number | '',
      validade: '',
      preco: '' as number | '',
    })),
})
const salvando = ref(false)
const erro = ref<string | null>(null)

async function receber() {
  const chegaram = form.linhas.filter((l) => l.quantidade !== '' && Number(l.quantidade) > 0)
  if (!chegaram.length) {
    erro.value = 'Informe a quantidade de pelo menos um item que chegou.'
    return
  }
  salvando.value = true
  erro.value = null
  try {
    const resultado = await api.receberPedido(props.pedido.id, {
      data: form.data,
      itens: chegaram.map((l) => ({
        item_id: l.item.id,
        quantidade: Number(l.quantidade),
        validade: l.validade || null,
        valor_unitario: l.preco === '' ? null : Number(l.preco),
      })),
    })
    emit('recebido', resultado)
  } catch (falha) {
    erro.value = mensagemDeErro(falha)
  } finally {
    salvando.value = false
  }
}
</script>

<template>
  <JanelaModal
    :titulo="`Receber o pedido nº ${pedido.id}`"
    @fechar="emit('fechar')"
  >
    <form
      class="grid gap-4"
      data-teste="receber"
      @submit.prevent="receber"
    >
      <p class="text-sm text-stone-600">
        Confira no galpão o que chegou{{ pedido.fornecedor ? ` de ${pedido.fornecedor}` : '' }}.
        Cada item vira uma entrada no estoque. O que não chegou, deixe em branco: o pedido fica
        esperando o resto.
      </p>
      <label class="flutuante">
        <input
          v-model="form.data"
          type="date"
          required
          :max="hoje()"
          class="campo"
        >
        <span class="rotulo">Chegou em</span>
      </label>
      <div
        v-for="linha in form.linhas"
        :key="linha.item.id"
        class="grid gap-3 rounded-lg bg-stone-50 p-3"
        data-teste="linha-recebimento"
      >
        <p class="text-sm font-semibold text-stone-800">
          {{ linha.item.insumo }}
          <span class="font-normal text-stone-500">
            · faltam {{ numero(linha.item.falta_receber) }} {{ linha.item.unidade }}
          </span>
        </p>
        <div class="grid grid-cols-2 gap-3">
          <label class="flutuante">
            <input
              v-model.number="linha.quantidade"
              type="number"
              min="0"
              step="any"
              placeholder=" "
              class="campo"
            >
            <span class="rotulo">Chegou ({{ linha.item.unidade }})</span>
          </label>
          <label class="flutuante">
            <input
              v-model="linha.validade"
              type="date"
              class="campo"
            >
            <span class="rotulo">Validade <span class="font-normal text-stone-500">(se tiver)</span></span>
          </label>
          <label class="flutuante col-span-2">
            <input
              v-model.number="linha.preco"
              type="number"
              min="0.0001"
              step="any"
              inputmode="decimal"
              :placeholder="linha.item.valor_unitario ? String(linha.item.valor_unitario) : ' '"
              class="campo"
            >
            <span class="rotulo">Preço na nota <span class="font-normal text-stone-500">(se mudou)</span></span>
          </label>
        </div>
      </div>
      <p
        v-if="erro"
        role="alert"
        class="text-sm text-red-700"
      >
        {{ erro }}
      </p>
      <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <button
          type="button"
          class="botao-secundario"
          @click="emit('fechar')"
        >
          Cancelar
        </button>
        <button
          type="submit"
          class="botao-primario"
          :disabled="salvando"
        >
          {{ salvando ? 'Lançando…' : 'Lançar no estoque' }}
        </button>
      </div>
    </form>
  </JanelaModal>
</template>
