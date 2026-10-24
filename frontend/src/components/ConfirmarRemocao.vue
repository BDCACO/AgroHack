<script setup lang="ts">
import { ref } from 'vue'

import { mensagemDeErro } from '@/stores/estoque'

import JanelaModal from './JanelaModal.vue'

const props = defineProps<{
  titulo: string
  texto: string
  /** A remoção em si. Se falhar (ex.: regra da API), a mensagem fica na janela. */
  remover: () => Promise<void>
}>()
const emit = defineEmits<{ fechar: [] }>()

const ocupado = ref(false)
const erro = ref<string | null>(null)

async function confirmar() {
  ocupado.value = true
  erro.value = null
  try {
    await props.remover()
    emit('fechar')
  } catch (falha) {
    erro.value = mensagemDeErro(falha)
  } finally {
    ocupado.value = false
  }
}
</script>

<template>
  <JanelaModal
    :titulo="titulo"
    @fechar="emit('fechar')"
  >
    <p class="text-sm text-stone-600">
      {{ texto }}
    </p>
    <p
      v-if="erro"
      role="alert"
      class="mt-3 text-sm text-red-700"
    >
      {{ erro }}
    </p>
    <!-- Cancelar vem primeiro e recebe o foco: um Enter distraído não apaga nada. -->
    <div class="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <button
        type="button"
        class="botao-secundario"
        autofocus
        @click="emit('fechar')"
      >
        Cancelar
      </button>
      <button
        type="button"
        class="botao-perigo border border-red-700/30"
        :disabled="ocupado"
        data-teste="confirmar-remocao"
        @click="confirmar"
      >
        {{ ocupado ? 'Removendo…' : 'Remover' }}
      </button>
    </div>
  </JanelaModal>
</template>
