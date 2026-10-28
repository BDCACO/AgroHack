<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import IconeSvg from '@/components/IconeSvg.vue'
import ListaDeSessoes from '@/components/ListaDeSessoes.vue'
import * as api from '@/services/sessao'
import { mensagemDeErro } from '@/stores/estoque'
import { useSessaoStore } from '@/stores/sessao'
import type { Sessao } from '@/types/api'

const sessao = useSessaoStore()
const rotuloDoPapel = { dono: 'Dono', funcionario: 'Funcionário' } as const

const sessoes = ref<Sessao[]>([])
const erroDasSessoes = ref<string | null>(null)
const aviso = ref<string | null>(null)

async function carregarSessoes() {
  erroDasSessoes.value = null
  try {
    sessoes.value = await api.listarMinhasSessoes()
  } catch (erro) {
    erroDasSessoes.value = mensagemDeErro(erro)
  }
}
onMounted(carregarSessoes)

async function encerrar(alvo: Sessao) {
  await api.encerrarMinhaSessao(alvo.id)
  sessoes.value = sessoes.value.filter((s) => s.id !== alvo.id)
}

const outras = computed(() => sessoes.value.filter((s) => !s.atual).length)
const encerrandoOutras = ref(false)
async function encerrarOutras() {
  encerrandoOutras.value = true
  aviso.value = null
  try {
    const quantas = await api.encerrarOutrasSessoes()
    aviso.value = quantas === 1 ? '1 aparelho saiu.' : `${quantas} aparelhos saíram.`
    await carregarSessoes()
  } catch (erro) {
    erroDasSessoes.value = mensagemDeErro(erro)
  } finally {
    encerrandoOutras.value = false
  }
}

const senha = reactive({ atual: '', nova: '', repetida: '' })
const trocando = ref(false)
const erroDaSenha = ref<string | null>(null)
const senhaTrocada = ref(false)

async function trocarSenha() {
  erroDaSenha.value = null
  senhaTrocada.value = false
  // Confere aqui o que a API não vê: ela recebe só a nova, uma vez.
  if (senha.nova !== senha.repetida) {
    erroDaSenha.value = 'A senha nova e a repetição não são iguais.'
    return
  }
  trocando.value = true
  try {
    await api.trocarSenha(senha.atual, senha.nova)
    Object.assign(senha, { atual: '', nova: '', repetida: '' })
    senhaTrocada.value = true
    // A troca tira os outros aparelhos.
    await carregarSessoes()
  } catch (erro) {
    erroDaSenha.value = mensagemDeErro(erro)
  } finally {
    trocando.value = false
  }
}
</script>

<template>
  <CabecalhoDePagina
    titulo="Minha conta"
    descricao="Sua senha e os aparelhos em que você está conectado."
  />

  <div
    v-if="sessao.usuario"
    class="grid animate-surgir gap-6 lg:grid-cols-2"
  >
    <section class="cartao p-5">
      <h2 class="text-base font-semibold text-stone-900">
        {{ sessao.usuario.nome }}
      </h2>
      <p
        class="text-sm text-stone-500"
        data-teste="quem"
      >
        Login {{ sessao.usuario.login }} · {{ rotuloDoPapel[sessao.usuario.papel] }}
      </p>

      <form
        class="mt-5 grid gap-4"
        data-teste="trocar-senha"
        @submit.prevent="trocarSenha"
      >
        <h3 class="text-sm font-semibold text-stone-800">
          Trocar a senha
        </h3>
        <label class="flutuante">
          <input
            v-model="senha.atual"
            type="password"
            required
            autocomplete="current-password"
            placeholder=" "
            class="campo"
          >
          <span class="rotulo">Senha atual</span>
        </label>
        <label class="flutuante">
          <input
            v-model="senha.nova"
            type="password"
            required
            minlength="8"
            maxlength="200"
            autocomplete="new-password"
            placeholder=" "
            class="campo"
          >
          <span class="rotulo">Senha nova <span class="font-normal text-stone-500">(8 ou mais caracteres)</span></span>
        </label>
        <label class="flutuante">
          <input
            v-model="senha.repetida"
            type="password"
            required
            autocomplete="new-password"
            placeholder=" "
            class="campo"
          >
          <span class="rotulo">Repita a senha nova</span>
        </label>
        <p
          v-if="erroDaSenha"
          role="alert"
          class="text-sm text-red-700"
        >
          {{ erroDaSenha }}
        </p>
        <p
          v-if="senhaTrocada"
          role="status"
          class="flex items-center gap-1.5 text-sm text-campo-700"
        >
          <IconeSvg
            nome="confirmado"
            class="h-4 w-4 shrink-0"
          />
          Senha trocada. Os outros aparelhos saíram; este continua conectado.
        </p>
        <div>
          <button
            type="submit"
            class="botao-primario"
            :disabled="trocando"
          >
            {{ trocando ? 'Trocando…' : 'Trocar senha' }}
          </button>
        </div>
      </form>
    </section>

    <section class="cartao p-5">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 class="text-base font-semibold text-stone-900">
            Onde você está conectado
          </h2>
          <p class="text-sm text-stone-500">
            Não reconhece um aparelho, ou perdeu o celular? Encerre a sessão dele.
          </p>
        </div>
        <button
          v-if="outras"
          type="button"
          class="botao-secundario"
          :disabled="encerrandoOutras"
          @click="encerrarOutras"
        >
          Sair dos outros aparelhos
        </button>
      </div>
      <p
        v-if="erroDasSessoes"
        role="alert"
        class="mt-3 text-sm text-red-700"
      >
        {{ erroDasSessoes }}
      </p>
      <p
        v-if="aviso"
        role="status"
        class="mt-3 text-sm text-campo-700"
      >
        {{ aviso }}
      </p>
      <ListaDeSessoes
        class="mt-2"
        :sessoes="sessoes"
        :encerrar="encerrar"
      />
    </section>
  </div>
</template>
