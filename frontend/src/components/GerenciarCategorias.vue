<script setup lang="ts">
import { ref } from 'vue'

import { mensagemDeErro } from '@/stores/estoque'
import { useCategoriasStore } from '@/stores/categorias'
import type { Categoria } from '@/types/api'

import JanelaModal from './JanelaModal.vue'

const emit = defineEmits<{ fechar: [] }>()
const categorias = useCategoriasStore()

const nova = ref('')
const editando = ref<{ id: number; nome: string } | null>(null)
const ocupado = ref(false)
const erro = ref<string | null>(null)

async function executar(acao: () => Promise<void>) {
  ocupado.value = true
  erro.value = null
  try {
    await acao()
  } catch (falha) {
    erro.value = mensagemDeErro(falha)
  } finally {
    ocupado.value = false
  }
}

const criar = () =>
  executar(async () => {
    await categorias.criar(nova.value)
    nova.value = ''
  })
const renomear = () =>
  executar(async () => {
    await categorias.renomear(editando.value!.id, editando.value!.nome)
    editando.value = null
  })
const remover = (categoria: Categoria) => executar(() => categorias.remover(categoria.id))
</script>

<template>
  <JanelaModal
    titulo="Categorias"
    @fechar="emit('fechar')"
  >
    <p class="text-sm text-stone-600">
      Separam a lista de insumos e o relatório: fertilizante, defensivo, nutrição animal…
    </p>

    <form
      class="mt-4 flex items-end gap-2"
      data-teste="nova-categoria"
      @submit.prevent="criar"
    >
      <label class="flutuante flex-1">
        <input
          v-model="nova"
          required
          maxlength="60"
          placeholder="Fertilizante"
          class="campo"
        >
        <span class="rotulo">Nova categoria</span>
      </label>
      <button
        type="submit"
        class="botao-primario h-12"
        :disabled="ocupado"
      >
        Criar
      </button>
    </form>

    <p
      v-if="erro"
      role="alert"
      class="mt-3 text-sm text-red-700"
    >
      {{ erro }}
    </p>

    <ul class="mt-3 divide-y divide-stone-100">
      <li
        v-for="categoria in categorias.categorias"
        :key="categoria.id"
        class="flex items-center gap-2 py-2"
        data-teste="categoria"
      >
        <form
          v-if="editando?.id === categoria.id"
          class="flex flex-1 items-center gap-2"
          @submit.prevent="renomear"
        >
          <input
            v-model="editando.nome"
            required
            maxlength="60"
            aria-label="Novo nome da categoria"
            class="campo mt-0 flex-1"
          >
          <button
            type="submit"
            class="botao-texto px-2"
            :disabled="ocupado"
          >
            Salvar
          </button>
        </form>
        <template v-else>
          <span class="flex-1 text-sm">
            <span class="font-medium text-stone-800">{{ categoria.nome }}</span>
            <span class="text-stone-500"> · {{ categoria.insumos === 1 ? '1 insumo' : `${categoria.insumos} insumos` }}</span>
          </span>
          <button
            type="button"
            class="botao-texto px-2 py-1"
            :aria-label="`Renomear ${categoria.nome}`"
            @click="editando = { id: categoria.id, nome: categoria.nome }; erro = null"
          >
            Renomear
          </button>
          <!-- Com insumos, a API recusa: o botão nem aparece. -->
          <button
            v-if="!categoria.insumos"
            type="button"
            class="botao-perigo px-2 py-1"
            :aria-label="`Remover ${categoria.nome}`"
            :disabled="ocupado"
            @click="remover(categoria)"
          >
            Remover
          </button>
        </template>
      </li>
    </ul>

    <div class="mt-4 flex justify-end">
      <button
        type="button"
        class="botao-secundario"
        @click="emit('fechar')"
      >
        Fechar
      </button>
    </div>
  </JanelaModal>
</template>
