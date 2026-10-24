<script setup lang="ts">
import { reactive, ref } from 'vue'

import { mensagemDeErro } from '@/services/http'
import { useInsumosStore } from '@/stores/insumos'
import type { Insumo } from '@/types/api'

import AvisoDeErro from './AvisoDeErro.vue'

/** `insumo` null = cadastro; preenchido = edição. */
const props = defineProps<{ insumo: Insumo | null }>()
const emit = defineEmits<{ salvo: []; cancelar: [] }>()

const insumos = useInsumosStore()

const campos = reactive({
  nome: props.insumo?.nome ?? '',
  categoria: props.insumo?.categoria ?? '',
  unidade: props.insumo?.unidade ?? '',
  // string: o <input type="number"> vazio é '', e '' não é 0.
  estoqueMinimo: props.insumo ? String(props.insumo.estoque_minimo) : '',
})
const salvando = ref(false)
const erro = ref<string | null>(null)

// Sugestões, não lista fechada: o produtor pode usar "saco 50 kg", "galão 20 L"...
const unidadesSugeridas = ['kg', 'g', 't', 'L', 'mL', 'unidade', 'saco', 'dose']

async function enviar() {
  salvando.value = true
  erro.value = null
  try {
    await insumos.salvar(props.insumo?.id ?? null, {
      nome: campos.nome,
      categoria: campos.categoria.trim() || null,
      unidade: campos.unidade,
      estoque_minimo: Number(campos.estoqueMinimo),
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
    <div>
      <label
        for="insumo-nome"
        class="rotulo"
      >Nome</label>
      <input
        id="insumo-nome"
        v-model="campos.nome"
        class="campo"
        required
        maxlength="120"
        placeholder="Ex.: Ureia"
      >
    </div>
    <div>
      <label
        for="insumo-categoria"
        class="rotulo"
      >Categoria <span class="font-normal text-stone-400">(opcional)</span></label>
      <input
        id="insumo-categoria"
        v-model="campos.categoria"
        class="campo"
        maxlength="80"
        placeholder="Ex.: Fertilizante"
      >
    </div>
    <div class="grid gap-4 sm:grid-cols-2">
      <div>
        <label
          for="insumo-unidade"
          class="rotulo"
        >Unidade</label>
        <input
          id="insumo-unidade"
          v-model="campos.unidade"
          class="campo"
          required
          maxlength="20"
          list="unidades-sugeridas"
          placeholder="Ex.: kg"
        >
        <datalist id="unidades-sugeridas">
          <option
            v-for="unidade in unidadesSugeridas"
            :key="unidade"
            :value="unidade"
          />
        </datalist>
      </div>
      <div>
        <label
          for="insumo-minimo"
          class="rotulo"
        >Estoque mínimo</label>
        <input
          id="insumo-minimo"
          v-model="campos.estoqueMinimo"
          class="campo"
          type="number"
          required
          min="0"
          step="any"
          inputmode="decimal"
        >
      </div>
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
        {{ salvando ? 'Salvando…' : 'Salvar' }}
      </button>
    </div>
  </form>
</template>
