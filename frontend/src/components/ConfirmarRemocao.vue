<script setup lang="ts">
import { ref } from 'vue'

import { mensagemDeErro } from '@/services/http'

import AvisoDeErro from './AvisoDeErro.vue'
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
    <AvisoDeErro
      v-if="erro"
      class="mt-4"
      :mensagem="erro"
    />
    <div class="mt-6 flex justify-end gap-2">
      <button
        type="button"
        class="botao-secundario"
        @click="emit('fechar')"
      >
        Cancelar
      </button>
      <button
        type="button"
        class="botao-perigo"
        :disabled="ocupado"
        @click="confirmar"
      >
        {{ ocupado ? 'Removendo…' : 'Remover' }}
      </button>
    </div>
  </JanelaModal>
</template>
