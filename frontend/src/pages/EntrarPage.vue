<script setup lang="ts">
import { onMounted, reactive, ref, useTemplateRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import LogoCampoCerto from '@/components/LogoCampoCerto.vue'
import { mensagemDeErro } from '@/stores/estoque'
import { useSessaoStore } from '@/stores/sessao'

const sessao = useSessaoStore()
const rota = useRoute()
const router = useRouter()

const form = reactive({ login: '', senha: '' })
const entrando = ref(false)
const erro = ref<string | null>(null)
const campoLogin = useTemplateRef<HTMLInputElement>('campoLogin')
onMounted(() => campoLogin.value?.focus())

// De onde a pessoa veio (a sessão caiu no meio do uso): depois de entrar, volta para lá.
// Só caminhos do próprio site: "?volta=https://..." não leva a outro endereço.
function destino() {
  const volta = rota.query.volta
  return typeof volta === 'string' && volta.startsWith('/') && !volta.startsWith('//')
    ? volta
    : '/'
}

async function entrar() {
  entrando.value = true
  erro.value = null
  try {
    await sessao.entrar(form.login, form.senha)
    await router.replace(destino())
  } catch (falha) {
    // A API responde a mesma frase para login inexistente, senha errada e bloqueio.
    erro.value = mensagemDeErro(falha)
    form.senha = ''
  } finally {
    entrando.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen flex-col items-center justify-center bg-linear-to-b from-campo-900 to-campo-950 px-4 py-10">
    <div class="mb-6 text-white">
      <LogoCampoCerto com-nome />
    </div>
    <form
      class="cartao w-full max-w-sm animate-surgir p-6"
      @submit.prevent="entrar"
    >
      <h1 class="text-lg font-semibold text-stone-900">
        Entrar
      </h1>
      <p class="mt-1 text-sm text-stone-600">
        Com o login e a senha que o dono da fazenda cadastrou para você.
      </p>
      <label class="flutuante mt-5">
        <input
          ref="campoLogin"
          v-model="form.login"
          required
          autocomplete="username"
          autocapitalize="none"
          spellcheck="false"
          placeholder=" "
          class="campo"
        >
        <span class="rotulo">Login</span>
      </label>
      <label class="flutuante mt-4">
        <input
          v-model="form.senha"
          type="password"
          required
          autocomplete="current-password"
          placeholder=" "
          class="campo"
        >
        <span class="rotulo">Senha</span>
      </label>
      <p
        v-if="erro"
        role="alert"
        class="mt-4 text-sm text-red-700"
      >
        {{ erro }}
      </p>
      <button
        type="submit"
        class="botao-primario mt-5 w-full"
        :disabled="entrando"
      >
        {{ entrando ? 'Entrando…' : 'Entrar' }}
      </button>
      <p class="mt-4 text-xs text-stone-500">
        Esqueceu a senha? O dono da fazenda pode definir uma nova para você.
      </p>
    </form>
  </div>
</template>
