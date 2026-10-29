<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import GradeDeMesesDeSafra from '@/components/GradeDeMesesDeSafra.vue'
import IconeSvg, { type NomeIcone } from '@/components/IconeSvg.vue'
import IndicadorDeStatus from '@/components/IndicadorDeStatus.vue'
import ListaDeSessoes from '@/components/ListaDeSessoes.vue'
import * as configuracao from '@/services/configuracao'
import * as api from '@/services/sessao'
import { mensagemDeErro } from '@/stores/estoque'
import { useSessaoStore } from '@/stores/sessao'
import { useStatusSistemaStore } from '@/stores/statusSistema'
import { escolherTema, type Tema, temaEscolhido } from '@/tema'
import type { Sessao } from '@/types/api'

// Tudo que é da pessoa e do aparelho num lugar só: o tema, o perfil, a senha, onde ela está
// conectada e se o sistema está no ar. Sem login (autenticação desligada), só o tema e o
// sistema: não há de quem ser o perfil.
const sessao = useSessaoStore()
const status = useStatusSistemaStore()
const rotuloDoPapel = { dono: 'Dono', funcionario: 'Funcionário' } as const

// ------------------------------------------------------------------ Aparência
const TEMAS: { valor: Tema; rotulo: string; icone: NomeIcone }[] = [
  { valor: 'claro', rotulo: 'Claro', icone: 'sol' },
  { valor: 'escuro', rotulo: 'Escuro', icone: 'lua' },
  { valor: 'sistema', rotulo: 'Igual ao aparelho', icone: 'aparelho' },
]

// ------------------------------------------------------------------ Calendário de safra
// Do dono (e do site sem login, que tem os poderes dele): os meses de safra da fazenda, que o
// motor de análise usa para não misturar o consumo da safra com o da entressafra.
const mesesDeSafra = ref<number[]>([])
const salvandoSafra = ref(false)
const safraSalva = ref(false)
const erroDaSafra = ref<string | null>(null)

watch(
  () => sessao.podeGerir,
  async (podeGerir) => {
    if (!podeGerir) return
    try {
      mesesDeSafra.value = (await configuracao.buscarConfiguracao()).meses_de_safra
    } catch (e) {
      erroDaSafra.value = mensagemDeErro(e)
    }
  },
  { immediate: true },
)

async function salvarSafra() {
  salvandoSafra.value = true
  safraSalva.value = false
  erroDaSafra.value = null
  try {
    mesesDeSafra.value = (
      await configuracao.salvarConfiguracao({ meses_de_safra: mesesDeSafra.value })
    ).meses_de_safra
    safraSalva.value = true
  } catch (e) {
    erroDaSafra.value = mensagemDeErro(e)
  } finally {
    salvandoSafra.value = false
  }
}

// ------------------------------------------------------------------ Perfil
const perfil = reactive({ nome: '', login: '', senhaAtual: '' })
// Como a API compara: sem espaços nas pontas e em minúsculas.
const loginNovo = computed(() => perfil.login.trim().toLowerCase())
const trocandoLogin = computed(() => !!sessao.usuario && loginNovo.value !== sessao.usuario.login)
const salvandoPerfil = ref(false)
const erroDoPerfil = ref<string | null>(null)
const perfilSalvo = ref(false)

async function salvarPerfil() {
  erroDoPerfil.value = null
  perfilSalvo.value = false
  salvandoPerfil.value = true
  try {
    sessao.usuario = await api.alterarMeuPerfil({
      nome: perfil.nome,
      ...(trocandoLogin.value ? { login: loginNovo.value, senha_atual: perfil.senhaAtual } : {}),
    })
    Object.assign(perfil, { nome: sessao.usuario.nome, login: sessao.usuario.login, senhaAtual: '' })
    perfilSalvo.value = true
  } catch (erro) {
    erroDoPerfil.value = mensagemDeErro(erro)
  } finally {
    salvandoPerfil.value = false
  }
}

// ------------------------------------------------------------------ Senha
const senha = reactive({ atual: '', nova: '', repetida: '' })
const trocandoSenha = ref(false)
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
  trocandoSenha.value = true
  try {
    await api.trocarSenha(senha.atual, senha.nova)
    Object.assign(senha, { atual: '', nova: '', repetida: '' })
    senhaTrocada.value = true
    // A troca tira os outros aparelhos.
    await carregarSessoes()
  } catch (erro) {
    erroDaSenha.value = mensagemDeErro(erro)
  } finally {
    trocandoSenha.value = false
  }
}

// ------------------------------------------------------------------ Aparelhos
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
// Aberta pelo endereço, a página monta antes de o site saber quem entrou: o perfil e os
// aparelhos esperam o usuário chegar (e voltam ao que está gravado se ele mudar).
watch(
  () => sessao.usuario?.id,
  (id) => {
    if (id === undefined || !sessao.usuario) return
    Object.assign(perfil, { nome: sessao.usuario.nome, login: sessao.usuario.login, senhaAtual: '' })
    carregarSessoes()
  },
  { immediate: true },
)

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
</script>

<template>
  <CabecalhoDePagina titulo="Configurações" />

  <div class="grid animate-surgir grid-cols-1 gap-6 lg:grid-cols-2">
    <!-- Aparência -->
    <section
      class="cartao p-5"
      aria-labelledby="titulo-aparencia"
    >
      <h2
        id="titulo-aparencia"
        class="text-base font-semibold text-stone-900"
      >
        Aparência
      </h2>
      <p class="mt-0.5 text-sm text-stone-500">
        Vale para este navegador.
      </p>
      <div
        class="mt-4 grid grid-cols-3 gap-2"
        role="radiogroup"
        aria-label="Tema"
      >
        <button
          v-for="opcao in TEMAS"
          :key="opcao.valor"
          type="button"
          role="radio"
          class="flex flex-col items-center gap-2 rounded-lg border px-2 py-3 text-sm font-medium transition-colors"
          :class="temaEscolhido === opcao.valor
            ? 'border-campo-600 bg-campo-50 text-campo-800 ring-1 ring-campo-600'
            : 'border-stone-200 text-stone-700 hover:border-stone-300 hover:bg-stone-50'"
          :aria-checked="temaEscolhido === opcao.valor"
          :data-teste="`tema-${opcao.valor}`"
          @click="escolherTema(opcao.valor)"
        >
          <IconeSvg
            :nome="opcao.icone"
            class="h-6 w-6"
          />
          <span class="text-center leading-tight">{{ opcao.rotulo }}</span>
        </button>
      </div>
    </section>

    <!-- Sistema: se a API e o banco estão no ar -->
    <section
      class="cartao p-5"
      aria-labelledby="titulo-sistema"
      data-teste="sistema"
    >
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2
            id="titulo-sistema"
            class="text-base font-semibold text-stone-900"
          >
            Sistema
          </h2>
          <p
            v-if="status.verificadoEm"
            class="mt-0.5 text-sm text-stone-500"
          >
            Última verificação: {{ status.verificadoEm.toLocaleTimeString('pt-BR') }}
          </p>
        </div>
        <button
          type="button"
          class="botao-secundario"
          :disabled="status.verificando"
          @click="status.verificar()"
        >
          <!-- Gira enquanto verifica: o pedido está andando. -->
          <IconeSvg
            nome="atualizar"
            class="h-4 w-4"
            :class="status.verificando ? 'animate-spin' : ''"
          />
          {{ status.verificando ? 'Verificando…' : 'Verificar de novo' }}
        </button>
      </div>
      <div class="mt-2 divide-y divide-stone-100">
        <IndicadorDeStatus
          rotulo="API"
          :estado="status.api"
        />
        <IndicadorDeStatus
          rotulo="Banco de dados"
          :estado="status.banco"
        />
      </div>
    </section>

    <!-- Calendário de safra (do dono) -->
    <section
      v-if="sessao.podeGerir"
      class="cartao p-5"
      aria-labelledby="titulo-safra"
      data-teste="calendario-de-safra"
    >
      <h2
        id="titulo-safra"
        class="text-base font-semibold text-stone-900"
      >
        Calendário de safra
      </h2>
      <p class="mt-0.5 text-sm text-stone-500">
        Marque os meses de safra. Com isso, o motor de análise não confunde consumo de
        entressafra com o ritmo da safra, e os alertas de estoque mínimo ficam menos urgentes
        fora de época. Vazio: a análise ignora a época do ano, como sempre.
      </p>
      <GradeDeMesesDeSafra
        v-model="mesesDeSafra"
        class="mt-3"
      />
      <p
        v-if="erroDaSafra"
        role="alert"
        class="mt-3 text-sm text-red-700"
      >
        {{ erroDaSafra }}
      </p>
      <div class="mt-4 flex items-center gap-3">
        <button
          type="button"
          data-teste="salvar-calendario"
          class="botao-primario"
          :disabled="salvandoSafra"
          @click="salvarSafra"
        >
          {{ salvandoSafra ? 'Salvando…' : 'Salvar' }}
        </button>
        <span
          v-if="safraSalva"
          role="status"
          class="text-sm text-campo-700"
        >Salvo.</span>
      </div>
    </section>

    <template v-if="sessao.usuario">
      <!-- Perfil -->
      <section
        class="cartao p-5"
        aria-labelledby="titulo-perfil"
      >
        <h2
          id="titulo-perfil"
          class="text-base font-semibold text-stone-900"
        >
          Perfil
        </h2>
        <p
          class="mt-0.5 text-sm text-stone-500"
          data-teste="quem"
        >
          {{ rotuloDoPapel[sessao.usuario.papel] }}<template v-if="sessao.usuario.papel === 'funcionario'">
            · o papel, só o dono muda
          </template>
        </p>
        <form
          class="mt-4 grid gap-4"
          data-teste="perfil"
          @submit.prevent="salvarPerfil"
        >
          <label class="flutuante">
            <input
              v-model="perfil.nome"
              required
              maxlength="120"
              autocomplete="name"
              placeholder=" "
              class="campo"
              data-teste="perfil-nome"
            >
            <span class="rotulo">Nome</span>
          </label>
          <label class="flutuante">
            <input
              v-model="perfil.login"
              required
              minlength="2"
              maxlength="40"
              pattern="\s*[A-Za-z0-9._\-]+\s*"
              autocomplete="username"
              autocapitalize="none"
              spellcheck="false"
              placeholder=" "
              class="campo"
              data-teste="perfil-login"
            >
            <span class="rotulo">Login <span class="font-normal text-stone-500">(letras sem acento, números, . - _)</span></span>
          </label>
          <!-- O login é com o que se entra: trocá-lo pede a senha de agora. -->
          <label
            v-if="trocandoLogin"
            class="flutuante"
          >
            <input
              v-model="perfil.senhaAtual"
              type="password"
              required
              autocomplete="current-password"
              placeholder=" "
              class="campo"
              data-teste="perfil-senha"
            >
            <span class="rotulo">Senha atual, para trocar o login</span>
          </label>
          <p
            v-if="erroDoPerfil"
            role="alert"
            class="text-sm text-red-700"
          >
            {{ erroDoPerfil }}
          </p>
          <p
            v-if="perfilSalvo"
            role="status"
            class="flex items-center gap-1.5 text-sm text-campo-700"
          >
            <IconeSvg
              nome="confirmado"
              class="h-4 w-4 shrink-0"
            />
            Perfil salvo.
          </p>
          <div>
            <button
              type="submit"
              class="botao-primario"
              :disabled="salvandoPerfil"
            >
              {{ salvandoPerfil ? 'Salvando…' : 'Salvar perfil' }}
            </button>
          </div>
        </form>
      </section>

      <!-- Senha -->
      <section
        class="cartao p-5"
        aria-labelledby="titulo-senha"
      >
        <h2
          id="titulo-senha"
          class="text-base font-semibold text-stone-900"
        >
          Senha
        </h2>
        <form
          class="mt-4 grid gap-4"
          data-teste="trocar-senha"
          @submit.prevent="trocarSenha"
        >
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
              :disabled="trocandoSenha"
            >
              {{ trocandoSenha ? 'Trocando…' : 'Trocar senha' }}
            </button>
          </div>
        </form>
      </section>

      <!-- Aparelhos -->
      <section
        class="cartao p-5 lg:col-span-2"
        aria-labelledby="titulo-aparelhos"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2
              id="titulo-aparelhos"
              class="text-base font-semibold text-stone-900"
            >
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
    </template>
  </div>
</template>
