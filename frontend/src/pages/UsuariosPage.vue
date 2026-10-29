<script setup lang="ts">
import { nextTick, onMounted, reactive, ref, useTemplateRef } from 'vue'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import JanelaModal from '@/components/JanelaModal.vue'
import ListaDeSessoes from '@/components/ListaDeSessoes.vue'
import { dataHora } from '@/formatos'
import * as api from '@/services/usuarios'
import { mensagemDeErro } from '@/stores/estoque'
import { useSessaoStore } from '@/stores/sessao'
import type { Papel, Sessao, UsuarioCompleto } from '@/types/api'

const sessao = useSessaoStore()
const rotuloDoPapel = { dono: 'Dono', funcionario: 'Funcionário' } as const

const usuarios = ref<UsuarioCompleto[]>([])
const carregado = ref(false)
const erro = ref<string | null>(null)

async function carregar() {
  erro.value = null
  try {
    usuarios.value = await api.listarUsuarios()
    carregado.value = true
  } catch (falha) {
    erro.value = mensagemDeErro(falha)
  }
}
onMounted(carregar)

// Cadastro e alteração no mesmo formulário: na alteração, login e senha não mudam (a senha
// tem o botão próprio, que derruba as sessões).
const vazio = { nome: '', login: '', senha: '', papel: 'funcionario' as Papel }
const form = reactive({ ...vazio })
const aberto = ref(false)
const editando = ref<UsuarioCompleto | null>(null)
const salvando = ref(false)
const erroDoForm = ref<string | null>(null)
const tituloDoForm = useTemplateRef<HTMLElement>('tituloDoForm')

function abrir(usuario?: UsuarioCompleto) {
  Object.assign(form, usuario ? { ...vazio, nome: usuario.nome, papel: usuario.papel } : vazio)
  editando.value = usuario ?? null
  erroDoForm.value = null
  aberto.value = true
  nextTick(() => tituloDoForm.value?.focus())
}

async function salvar() {
  salvando.value = true
  erroDoForm.value = null
  try {
    if (editando.value) {
      await api.alterarUsuario(editando.value.id, { nome: form.nome, papel: form.papel })
    } else {
      await api.criarUsuario({ ...form, login: form.login.trim().toLowerCase() })
    }
    aberto.value = false
    await carregar()
  } catch (falha) {
    erroDoForm.value = mensagemDeErro(falha)
  } finally {
    salvando.value = false
  }
}

// Desativar pede confirmação; reativar, não (não tira ninguém de nada).
const emDesativacao = ref<UsuarioCompleto | null>(null)
const ocupado = ref(false)
const erroDaJanela = ref<string | null>(null)

async function mudarAtivo(usuario: UsuarioCompleto, ativo: boolean) {
  ocupado.value = true
  erroDaJanela.value = null
  try {
    await api.alterarUsuario(usuario.id, { ativo })
    emDesativacao.value = null
    await carregar()
  } catch (falha) {
    // O último dono não se desativa: a frase da API diz por quê.
    if (emDesativacao.value) erroDaJanela.value = mensagemDeErro(falha)
    else erro.value = mensagemDeErro(falha)
  } finally {
    ocupado.value = false
  }
}

const emNovaSenha = ref<UsuarioCompleto | null>(null)
const senhaNova = ref('')
const senhaDefinida = ref<string | null>(null)
async function definirSenha() {
  if (!emNovaSenha.value) return
  ocupado.value = true
  erroDaJanela.value = null
  try {
    await api.redefinirSenha(emNovaSenha.value.id, senhaNova.value)
    senhaDefinida.value = emNovaSenha.value.nome
    emNovaSenha.value = null
    await carregar()
  } catch (falha) {
    erroDaJanela.value = mensagemDeErro(falha)
  } finally {
    ocupado.value = false
  }
}
function abrirNovaSenha(usuario: UsuarioCompleto) {
  senhaNova.value = ''
  erroDaJanela.value = null
  senhaDefinida.value = null
  emNovaSenha.value = usuario
}

// Os aparelhos de alguém: o celular perdido do funcionário se encerra sem desativá-lo.
const deQuem = ref<UsuarioCompleto | null>(null)
const sessoes = ref<Sessao[]>([])
async function abrirAparelhos(usuario: UsuarioCompleto) {
  deQuem.value = usuario
  sessoes.value = []
  erroDaJanela.value = null
  try {
    sessoes.value = await api.listarSessoesDe(usuario.id)
  } catch (falha) {
    erroDaJanela.value = mensagemDeErro(falha)
  }
}
async function encerrarSessao(alvo: Sessao) {
  await api.encerrarSessaoDe(deQuem.value!.id, alvo.id)
  sessoes.value = sessoes.value.filter((s) => s.id !== alvo.id)
}
async function encerrarTodas() {
  ocupado.value = true
  try {
    await api.encerrarSessoesDe(deQuem.value!.id)
    sessoes.value = await api.listarSessoesDe(deQuem.value!.id)
  } catch (falha) {
    erroDaJanela.value = mensagemDeErro(falha)
  } finally {
    ocupado.value = false
  }
}

const bloqueado = (usuario: UsuarioCompleto) =>
  usuario.bloqueado_ate !== null && new Date(usuario.bloqueado_ate).getTime() > Date.now()
</script>

<template>
  <CabecalhoDePagina
    titulo="Usuários"
  >
    <template #acoes>
      <button
        type="button"
        class="botao-primario"
        @click="abrir()"
      >
        Novo usuário
      </button>
    </template>
  </CabecalhoDePagina>

  <form
    v-if="aberto"
    class="cartao mt-2 mb-6 grid animate-surgir items-end gap-4 p-5 sm:grid-cols-2 lg:grid-cols-4"
    @submit.prevent="salvar"
  >
    <h2
      ref="tituloDoForm"
      tabindex="-1"
      class="text-base font-semibold text-stone-900 focus:outline-none sm:col-span-2 lg:col-span-4"
    >
      {{ editando ? `Alterar ${editando.nome}` : 'Novo usuário' }}
    </h2>
    <label class="flutuante">
      <input
        v-model="form.nome"
        required
        maxlength="120"
        placeholder="Zé do Campo"
        class="campo"
      >
      <span class="rotulo">Nome</span>
    </label>
    <template v-if="!editando">
      <label class="flutuante">
        <input
          v-model="form.login"
          required
          pattern="[a-z0-9._\-]{2,40}"
          title="Letras minúsculas sem acento, números, ponto, hífen ou sublinhado (2 a 40)"
          autocapitalize="none"
          spellcheck="false"
          autocomplete="off"
          placeholder="ze"
          class="campo"
        >
        <span class="rotulo">Login</span>
      </label>
      <label class="flutuante">
        <input
          v-model="form.senha"
          type="password"
          required
          minlength="8"
          maxlength="200"
          autocomplete="new-password"
          placeholder=" "
          class="campo"
        >
        <span class="rotulo">Senha inicial <span class="font-normal text-stone-500">(8 ou mais)</span></span>
      </label>
    </template>
    <label class="flutuante">
      <select
        v-model="form.papel"
        class="campo"
      >
        <option value="funcionario">
          Funcionário: lança e consulta
        </option>
        <option value="dono">
          Dono: também cadastra, remove e compra
        </option>
      </select>
      <span class="rotulo">Papel</span>
    </label>
    <p
      v-if="!editando"
      class="text-xs text-stone-500 sm:col-span-2 lg:col-span-4"
    >
      Passe o login e a senha inicial para a pessoa. Ela troca a senha depois, em Minha conta.
    </p>
    <p
      v-if="erroDoForm"
      role="alert"
      class="text-sm text-red-700 sm:col-span-2 lg:col-span-4"
    >
      {{ erroDoForm }}
    </p>
    <div class="flex gap-2 sm:col-span-2 lg:col-span-4">
      <button
        type="submit"
        class="botao-primario"
        :disabled="salvando"
      >
        {{ salvando ? 'Salvando…' : 'Salvar' }}
      </button>
      <button
        type="button"
        class="botao-texto text-stone-700 hover:bg-stone-100"
        @click="aberto = false"
      >
        Cancelar
      </button>
    </div>
  </form>

  <p
    v-if="erro"
    role="alert"
    class="mt-4 text-sm text-red-700"
  >
    {{ erro }}
  </p>
  <p
    v-if="senhaDefinida"
    role="status"
    class="mb-4 text-sm text-campo-700"
  >
    Senha nova de {{ senhaDefinida }} definida. Os aparelhos dele saíram; ele entra com a senha nova.
  </p>

  <ul
    v-if="carregado"
    class="cartao animate-surgir divide-y divide-stone-100"
  >
    <li
      v-for="usuario in usuarios"
      :key="usuario.id"
      class="flex flex-wrap items-center gap-x-4 gap-y-2 p-4"
      :class="usuario.ativo ? '' : 'bg-stone-50/70'"
      data-teste="usuario"
    >
      <div class="min-w-0 flex-1">
        <p
          class="font-semibold"
          :class="usuario.ativo ? 'text-stone-900' : 'text-stone-500'"
        >
          {{ usuario.nome }}
          <span
            v-if="usuario.id === sessao.usuario?.id"
            class="text-sm font-normal text-stone-500"
          >(você)</span>
        </p>
        <p class="text-sm text-stone-500">
          {{ usuario.login }} · {{ rotuloDoPapel[usuario.papel] }}
        </p>
      </div>
      <span
        v-if="!usuario.ativo"
        class="rounded-full bg-stone-100 px-2 py-0.5 text-xs font-semibold text-stone-600"
      >Desativado</span>
      <span
        v-else-if="bloqueado(usuario)"
        class="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-800 ring-1 ring-amber-500/30 ring-inset"
        :title="`Senhas erradas seguidas: bloqueado até ${dataHora(usuario.bloqueado_ate!)}`"
      >Bloqueado até {{ dataHora(usuario.bloqueado_ate!) }}</span>
      <div class="flex flex-wrap gap-1">
        <button
          type="button"
          class="botao-texto px-2 py-1"
          :aria-label="`Alterar ${usuario.nome}`"
          @click="abrir(usuario)"
        >
          Alterar
        </button>
        <button
          v-if="usuario.ativo"
          type="button"
          class="botao-texto px-2 py-1"
          :aria-label="`Aparelhos de ${usuario.nome}`"
          @click="abrirAparelhos(usuario)"
        >
          Aparelhos
        </button>
        <button
          type="button"
          class="botao-texto px-2 py-1"
          :aria-label="`Nova senha para ${usuario.nome}`"
          @click="abrirNovaSenha(usuario)"
        >
          Nova senha
        </button>
        <button
          v-if="usuario.ativo && usuario.id !== sessao.usuario?.id"
          type="button"
          class="botao-perigo px-2 py-1"
          :aria-label="`Desativar ${usuario.nome}`"
          @click="emDesativacao = usuario; erroDaJanela = null"
        >
          Desativar
        </button>
        <button
          v-else-if="!usuario.ativo"
          type="button"
          class="botao-texto px-2 py-1"
          :aria-label="`Reativar ${usuario.nome}`"
          @click="mudarAtivo(usuario, true)"
        >
          Reativar
        </button>
      </div>
    </li>
  </ul>

  <JanelaModal
    v-if="emDesativacao"
    titulo="Desativar usuário"
    @fechar="emDesativacao = null"
  >
    <p class="text-sm text-stone-600">
      Desativar {{ emDesativacao.nome }}? Ele sai de todos os aparelhos e não entra mais. O que
      ele lançou continua, com o nome dele. Dá para reativar depois.
    </p>
    <p
      v-if="erroDaJanela"
      role="alert"
      class="mt-3 text-sm text-red-700"
    >
      {{ erroDaJanela }}
    </p>
    <div class="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <button
        type="button"
        class="botao-secundario"
        autofocus
        @click="emDesativacao = null"
      >
        Cancelar
      </button>
      <button
        type="button"
        class="botao-perigo border border-red-700/30"
        :disabled="ocupado"
        data-teste="confirmar-desativacao"
        @click="mudarAtivo(emDesativacao, false)"
      >
        Desativar
      </button>
    </div>
  </JanelaModal>

  <JanelaModal
    v-if="emNovaSenha"
    :titulo="`Nova senha para ${emNovaSenha.nome}`"
    @fechar="emNovaSenha = null"
  >
    <form
      class="grid gap-4"
      data-teste="nova-senha"
      @submit.prevent="definirSenha"
    >
      <p class="text-sm text-stone-600">
        Para quem esqueceu a senha ou ficou bloqueado. Os aparelhos dele saem, e o bloqueio por
        senhas erradas acaba.
      </p>
      <label class="flutuante">
        <input
          v-model="senhaNova"
          type="password"
          required
          minlength="8"
          maxlength="200"
          autocomplete="new-password"
          placeholder=" "
          class="campo"
        >
        <span class="rotulo">Senha nova <span class="font-normal text-stone-500">(8 ou mais)</span></span>
      </label>
      <p
        v-if="erroDaJanela"
        role="alert"
        class="text-sm text-red-700"
      >
        {{ erroDaJanela }}
      </p>
      <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <button
          type="button"
          class="botao-secundario"
          @click="emNovaSenha = null"
        >
          Cancelar
        </button>
        <button
          type="submit"
          class="botao-primario"
          :disabled="ocupado"
        >
          Definir senha
        </button>
      </div>
    </form>
  </JanelaModal>

  <JanelaModal
    v-if="deQuem"
    :titulo="`Aparelhos de ${deQuem.nome}`"
    @fechar="deQuem = null"
  >
    <p
      v-if="erroDaJanela"
      role="alert"
      class="text-sm text-red-700"
    >
      {{ erroDaJanela }}
    </p>
    <p
      v-else-if="!sessoes.length"
      class="text-sm text-stone-500"
    >
      Nenhum aparelho conectado.
    </p>
    <ListaDeSessoes
      :sessoes="sessoes"
      :encerrar="encerrarSessao"
    />
    <div class="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <button
        type="button"
        class="botao-secundario"
        autofocus
        @click="deQuem = null"
      >
        Fechar
      </button>
      <button
        v-if="sessoes.some((s) => !s.atual)"
        type="button"
        class="botao-perigo border border-red-700/30"
        :disabled="ocupado"
        @click="encerrarTodas"
      >
        Encerrar todos
      </button>
    </div>
  </JanelaModal>
</template>
