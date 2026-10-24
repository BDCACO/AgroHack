<script setup lang="ts">
import { computed, reactive, ref } from 'vue'

import { formatarQuantidade, hojeIso } from '@/formatos'
import { mensagemDeErro } from '@/services/http'
import { useInsumosStore } from '@/stores/insumos'
import { useMovimentacoesStore } from '@/stores/movimentacoes'
import type { TipoMovimentacao } from '@/types/api'

import AvisoDeErro from './AvisoDeErro.vue'

const props = defineProps<{ insumoInicialId?: string | null }>()
const emit = defineEmits<{ salvo: []; cancelar: [] }>()

const insumos = useInsumosStore()
const movimentacoes = useMovimentacoesStore()

const campos = reactive({
  insumoId: props.insumoInicialId ?? '',
  tipo: 'compra' as TipoMovimentacao,
  quantidade: '',
  data: hojeIso(),
  validade: '',
  observacao: '',
})
const salvando = ref(false)
const erro = ref<string | null>(null)

const insumoEscolhido = computed(() => insumos.lista.find((i) => i.id === campos.insumoId))

async function enviar() {
  salvando.value = true
  erro.value = null
  try {
    await movimentacoes.registrar({
      insumo_id: campos.insumoId,
      tipo: campos.tipo,
      quantidade: Number(campos.quantidade),
      data: campos.data,
      // Validade só existe em compra; a API recusa em retirada.
      validade: campos.tipo === 'compra' && campos.validade ? campos.validade : null,
      observacao: campos.observacao.trim() || null,
    })
    emit('salvo')
  } catch (falha) {
    erro.value = mensagemDeErro(falha)
  } finally {
    salvando.value = false
  }
}
</script>

<template>
  <form
    class="space-y-4"
    @submit.prevent="enviar"
  >
    <fieldset>
      <legend class="rotulo">
        Tipo
      </legend>
      <div class="mt-1 grid grid-cols-2 gap-2">
        <label
          v-for="opcao in [
            { valor: 'compra', rotulo: 'Compra (entrada)' },
            { valor: 'retirada', rotulo: 'Retirada (saída)' },
          ] as const"
          :key="opcao.valor"
          class="flex cursor-pointer items-center justify-center rounded-md border px-3 py-2 text-sm font-medium"
          :class="
            campos.tipo === opcao.valor
              ? 'border-campo-600 bg-campo-50 text-campo-900'
              : 'border-stone-300 text-stone-600 hover:bg-stone-50'
          "
        >
          <input
            v-model="campos.tipo"
            type="radio"
            name="tipo"
            class="sr-only"
            :value="opcao.valor"
          >
          {{ opcao.rotulo }}
        </label>
      </div>
    </fieldset>

    <div>
      <label
        for="mov-insumo"
        class="rotulo"
      >Insumo</label>
      <select
        id="mov-insumo"
        v-model="campos.insumoId"
        class="campo"
        required
      >
        <option
          value=""
          disabled
        >
          Escolha o insumo
        </option>
        <option
          v-for="insumo in insumos.lista"
          :key="insumo.id"
          :value="insumo.id"
        >
          {{ insumo.nome }}
        </option>
      </select>
      <p
        v-if="insumoEscolhido"
        class="mt-1 text-xs text-stone-500"
        data-teste="saldo-disponivel"
      >
        Saldo atual: {{ formatarQuantidade(insumoEscolhido.saldo_atual) }} {{ insumoEscolhido.unidade }}
      </p>
    </div>

    <div class="grid gap-4 sm:grid-cols-2">
      <div>
        <label
          for="mov-quantidade"
          class="rotulo"
        >Quantidade<template v-if="insumoEscolhido"> ({{ insumoEscolhido.unidade }})</template></label>
        <input
          id="mov-quantidade"
          v-model="campos.quantidade"
          class="campo"
          type="number"
          required
          min="0"
          step="any"
          inputmode="decimal"
        >
      </div>
      <div>
        <label
          for="mov-data"
          class="rotulo"
        >Data</label>
        <input
          id="mov-data"
          v-model="campos.data"
          class="campo"
          type="date"
          required
        >
      </div>
    </div>

    <div v-if="campos.tipo === 'compra'">
      <label
        for="mov-validade"
        class="rotulo"
      >Validade do lote <span class="font-normal text-stone-400">(opcional)</span></label>
      <input
        id="mov-validade"
        v-model="campos.validade"
        class="campo"
        type="date"
      >
    </div>

    <div>
      <label
        for="mov-observacao"
        class="rotulo"
      >Observação <span class="font-normal text-stone-400">(opcional)</span></label>
      <input
        id="mov-observacao"
        v-model="campos.observacao"
        class="campo"
        maxlength="500"
        placeholder="Ex.: talhão 3, nota fiscal 1234"
      >
    </div>

    <AvisoDeErro
      v-if="erro"
      :mensagem="erro"
    />

    <div class="flex justify-end gap-2 pt-2">
      <button
        type="button"
        class="botao-secundario"
        @click="emit('cancelar')"
      >
        Cancelar
      </button>
      <button
        type="submit"
        class="botao-primario"
        :disabled="salvando"
      >
        {{ salvando ? 'Registrando…' : 'Registrar' }}
      </button>
    </div>
  </form>
</template>
