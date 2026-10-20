<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
import SeloDeGravidade from '@/components/SeloDeGravidade.vue'
import { mensagemDeErro, useEstoqueStore } from '@/stores/estoque'
import type { Insumo } from '@/types/api'

const estoque = useEstoqueStore()
onMounted(() => estoque.carregar())

// Input numérico vazio vale '' no v-model; '' = "não informado" (null na API).
const vazio = { nome: '', unidade: '', estoque_minimo: '' as number | '', prazo: '' as number | '' }
const form = reactive({ ...vazio })
const aberto = ref(false)
const editandoId = ref<number>()
const salvando = ref(false)
const erroDoForm = ref<string | null>(null)

function abrir(insumo?: Insumo) {
  Object.assign(
    form,
    insumo
      ? {
          nome: insumo.nome,
          unidade: insumo.unidade,
          estoque_minimo: insumo.estoque_minimo ?? '',
          prazo: insumo.prazo_reposicao_dias ?? '',
        }
      : vazio,
  )
  editandoId.value = insumo?.id
  erroDoForm.value = null
  aberto.value = true
}

async function salvar() {
  salvando.value = true
  erroDoForm.value = null
  try {
    await estoque.salvarInsumo(
      {
        nome: form.nome,
        unidade: form.unidade,
        estoque_minimo: form.estoque_minimo === '' ? null : form.estoque_minimo,
        prazo_reposicao_dias: form.prazo === '' ? null : form.prazo,
      },
      editandoId.value,
    )
    aberto.value = false
  } catch (erro) {
    erroDoForm.value = mensagemDeErro(erro)
  } finally {
    salvando.value = false
  }
}

const numero = (valor: number) => valor.toLocaleString('pt-BR', { maximumFractionDigits: 3 })
</script>

<template>
  <CabecalhoDePagina
    titulo="Insumos"
    descricao="Produtos em estoque: quantidade atual, mínimo e prazo de reposição."
  >
    <template #acoes>
      <button
        v-if="estoque.insumos.length"
        type="button"
        class="botao-primario"
        @click="abrir()"
      >
        Novo insumo
      </button>
    </template>
  </CabecalhoDePagina>

  <form
    v-if="aberto"
    class="cartao mt-2 mb-6 grid animate-surgir gap-4 p-5 sm:grid-cols-2 lg:grid-cols-4"
    @submit.prevent="salvar"
  >
    <h2 class="text-base font-semibold text-stone-900 sm:col-span-2 lg:col-span-4">
      {{ editandoId === undefined ? 'Novo insumo' : 'Alterar insumo' }}
    </h2>
    <label class="text-sm font-medium text-stone-700">
      Nome
      <input
        v-model="form.nome"
        required
        maxlength="120"
        placeholder="Ureia agrícola"
        class="campo"
      >
    </label>
    <label class="text-sm font-medium text-stone-700">
      Unidade
      <input
        v-model="form.unidade"
        required
        maxlength="20"
        list="unidades"
        placeholder="kg"
        class="campo"
      >
      <datalist id="unidades">
        <option value="kg" />
        <option value="L" />
        <option value="t" />
        <option value="sc" />
        <option value="dose" />
        <option value="un" />
      </datalist>
    </label>
    <label class="text-sm font-medium text-stone-700">
      Estoque mínimo <span class="font-normal text-stone-500">(opcional)</span>
      <input
        v-model.number="form.estoque_minimo"
        type="number"
        min="0"
        step="any"
        class="campo"
      >
    </label>
    <label class="text-sm font-medium text-stone-700">
      Prazo de entrega, em dias <span class="font-normal text-stone-500">(opcional)</span>
      <input
        v-model.number="form.prazo"
        type="number"
        min="0"
        max="365"
        step="1"
        class="campo"
      >
    </label>
    <p class="text-xs text-stone-500 sm:col-span-2 lg:col-span-4">
      O mínimo dispara o alerta de estoque baixo e vira margem de segurança na reposição. O prazo
      é quanto o fornecedor leva para entregar; sem ele, a análise assume 15 dias e avisa.
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
    v-if="estoque.erro"
    role="alert"
    class="mt-6 text-sm text-red-700"
  >
    {{ estoque.erro }}
  </p>

  <EstadoVazio
    v-else-if="estoque.carregado && !estoque.insumos.length && !aberto"
    icone="insumos"
    titulo="Nenhum insumo cadastrado"
    texto="Cadastre os produtos que você guarda no galpão: adubos, defensivos, sementes, sal mineral, vacinas…"
  >
    <button
      type="button"
      class="botao-primario"
      @click="abrir()"
    >
      Cadastrar insumo
    </button>
  </EstadoVazio>

  <div
    v-else-if="estoque.insumos.length"
    class="cartao animate-surgir overflow-x-auto"
  >
    <table class="w-full text-left text-sm">
      <thead class="bg-stone-50/80 text-xs tracking-wide text-stone-500 uppercase">
        <tr>
          <th class="px-4 py-3 font-semibold">
            Insumo
          </th>
          <th class="px-4 py-3 text-right font-semibold">
            Estoque atual
          </th>
          <th class="px-4 py-3 text-right font-semibold">
            Mínimo
          </th>
          <th class="px-4 py-3 text-right font-semibold">
            Prazo
          </th>
          <th class="px-4 py-3 font-semibold">
            Situação
          </th>
          <th class="px-4 py-3">
            <span class="sr-only">Ações</span>
          </th>
        </tr>
      </thead>
      <tbody class="divide-y divide-stone-100">
        <tr
          v-for="insumo in estoque.insumos"
          :key="insumo.id"
          class="transition-colors hover:bg-stone-50/70"
        >
          <td class="px-4 py-3 font-medium text-stone-800">
            <RouterLink
              :to="{ name: 'insumo', params: { id: insumo.id } }"
              class="hover:text-campo-700 hover:underline"
            >
              {{ insumo.nome }}
            </RouterLink>
          </td>
          <td
            class="px-4 py-3 text-right tabular-nums"
            :class="insumo.estoque_atual < 0 ? 'text-red-700' : ''"
          >
            {{ numero(insumo.estoque_atual) }} {{ insumo.unidade }}
          </td>
          <td class="px-4 py-3 text-right tabular-nums text-stone-600">
            {{ insumo.estoque_minimo === null ? '—' : `${numero(insumo.estoque_minimo)} ${insumo.unidade}` }}
          </td>
          <td class="px-4 py-3 text-right tabular-nums text-stone-600">
            {{ insumo.prazo_reposicao_dias === null ? '—' : `${insumo.prazo_reposicao_dias} dias` }}
          </td>
          <td class="px-4 py-3">
            <!-- A API já ordena os alertas do mais grave para o mais leve. -->
            <SeloDeGravidade :gravidade="insumo.analise.alertas[0]?.gravidade ?? null" />
          </td>
          <td class="px-4 py-3 text-right">
            <button
              type="button"
              class="rounded-md px-2 py-1 text-sm font-medium text-campo-700 transition-colors hover:bg-campo-50"
              @click="abrir(insumo)"
            >
              Alterar
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
