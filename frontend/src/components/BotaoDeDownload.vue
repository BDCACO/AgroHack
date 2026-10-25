<script setup lang="ts">
import { ref } from 'vue'

import { mensagemDeErro } from '@/stores/estoque'

import IconeSvg from './IconeSvg.vue'

// A classe e o data-teste de quem usa vão para o botão, não para o invólucro.
defineOptions({ inheritAttrs: false })

const props = defineProps<{
  rotulo: string
  /** O download em si (pelo cliente HTTP, que leva o token da sessão). */
  baixar: () => Promise<void>
}>()

const baixando = ref(false)
const erro = ref<string | null>(null)

async function clicar() {
  baixando.value = true
  erro.value = null
  try {
    await props.baixar()
  } catch (falha) {
    erro.value = mensagemDeErro(falha)
  } finally {
    baixando.value = false
  }
}
</script>

<template>
  <span class="inline-flex flex-col gap-1">
    <button
      type="button"
      v-bind="$attrs"
      :disabled="baixando"
      @click="clicar"
    >
      <IconeSvg
        nome="baixar"
        class="h-4 w-4"
      />
      {{ baixando ? 'Baixando…' : rotulo }}
    </button>
    <span
      v-if="erro"
      role="alert"
      class="text-xs text-red-700"
    >{{ erro }}</span>
  </span>
</template>
