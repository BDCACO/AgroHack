<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import ConfirmarRemocao from '@/components/ConfirmarRemocao.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
import IconeSvg from '@/components/IconeSvg.vue'
import JanelaModal from '@/components/JanelaModal.vue'
import { reais } from '@/formatos'
import { mensagemDeErro } from '@/stores/estoque'
import { useSessaoStore } from '@/stores/sessao'
import { useTalhoesStore } from '@/stores/talhoes'
import type { Talhao } from '@/types/api'

// Só exibe: carência, custo e limitações quem calcula é a API.
const talhoes = useTalhoesStore()
const sessao = useSessaoStore()
onMounted(() => talhoes.carregar())

// Input numérico vazio vale '' no v-model.
const vazio = { nome: '', area: '' as number | '', cultura: '' }
const form = reactive({ ...vazio })
const aberto = ref(false)
const editandoId = ref<number>()
const salvando = ref(false)
const erroDoForm = ref<string | null>(null)
const emRemocao = ref<Talhao | null>(null)

function abrir(talhao?: Talhao) {
  Object.assign(
    form,
    talhao ? { nome: talhao.nome, area: talhao.area_ha, cultura: talhao.cultura ?? '' } : vazio,
  )
  editandoId.value = talhao?.id
  erroDoForm.value = null
  // Numa janela: quem tocou em "Alterar" no fim da lista não perde o lugar.
  aberto.value = true
}

async function salvar() {
  if (form.area === '') return
  salvando.value = true
  erroDoForm.value = null
  try {
    await talhoes.salvar(
      { nome: form.nome, area_ha: form.area, cultura: form.cultura || null },
      editandoId.value,
    )
    aberto.value = false
  } catch (erro) {
    erroDoForm.value = mensagemDeErro(erro)
  } finally {
    salvando.value = false
  }
}

const numero = (valor: number) => valor.toLocaleString('pt-BR', { maximumFractionDigits: 2 })
const dataBr = (data: string) => data.split('-').reverse().join('/')
</script>

<template>
  <CabecalhoDePagina
    titulo="Talhões"
    descricao="Onde cada insumo foi aplicado: até quando não colher (carência) e quanto custou por hectare."
  >
    <template #acoes>
      <button
        v-if="talhoes.talhoes.length && sessao.podeGerir"
        type="button"
        class="botao-primario"
        @click="abrir()"
      >
        Novo talhão
      </button>
    </template>
  </CabecalhoDePagina>

  <JanelaModal
    v-if="aberto"
    :titulo="editandoId === undefined ? 'Novo talhão' : 'Alterar talhão'"
    @fechar="aberto = false"
  >
    <form
      class="grid gap-4"
      data-teste="form-talhao"
      @submit.prevent="salvar"
    >
      <label class="flutuante">
        <input
          v-model="form.nome"
          autofocus
          required
          maxlength="120"
          placeholder="Talhão Norte"
          class="campo"
        >
        <span class="rotulo">Nome</span>
      </label>
      <label class="flutuante">
        <input
          v-model.number="form.area"
          type="number"
          required
          min="0.01"
          step="any"
          placeholder=" "
          class="campo"
        >
        <span class="rotulo">Área, em hectares</span>
      </label>
      <label class="flutuante">
        <input
          v-model="form.cultura"
          maxlength="60"
          list="culturas"
          placeholder="Soja"
          class="campo"
        >
        <span class="rotulo">Cultura <span class="font-normal text-stone-500">(opcional)</span></span>
        <datalist id="culturas">
          <option value="Soja" />
          <option value="Milho" />
          <option value="Café" />
          <option value="Pasto" />
          <option value="Feijão" />
        </datalist>
      </label>
      <p
        v-if="erroDoForm"
        role="alert"
        class="text-sm text-red-700"
      >
        {{ erroDoForm }}
      </p>
      <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <button
          type="button"
          class="botao-secundario"
          @click="aberto = false"
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
  </JanelaModal>

  <p
    v-if="talhoes.erro"
    role="alert"
    class="mt-6 text-sm text-red-700"
  >
    {{ talhoes.erro }}
  </p>

  <EstadoVazio
    v-else-if="talhoes.carregado && !talhoes.talhoes.length"
    icone="talhoes"
    titulo="Nenhum talhão cadastrado"
    :texto="sessao.podeGerir
      ? 'Cadastre as áreas da fazenda. Ao lançar uma retirada, diga onde aplicou: o CampoCerto avisa até quando não colher e soma o custo por hectare.'
      : 'Quando o dono da fazenda cadastrar os talhões, ao lançar uma retirada você diz onde aplicou.'"
  >
    <button
      v-if="sessao.podeGerir"
      type="button"
      class="botao-primario"
      @click="abrir()"
    >
      Cadastrar talhão
    </button>
  </EstadoVazio>

  <ul
    v-else-if="talhoes.talhoes.length"
    class="grid animate-surgir gap-3 md:grid-cols-2"
  >
    <li
      v-for="talhao in talhoes.talhoes"
      :key="talhao.id"
      class="cartao flex flex-col p-4"
      :class="talhao.em_carencia ? 'border-red-200' : ''"
      data-teste="talhao"
    >
      <div class="flex items-start gap-2">
        <div class="min-w-0 flex-1">
          <RouterLink
            :to="{ name: 'talhao', params: { id: talhao.id } }"
            class="font-semibold text-stone-900 hover:text-campo-700 hover:underline"
          >
            {{ talhao.nome }}
          </RouterLink>
          <p class="text-sm text-stone-500 tabular-nums">
            {{ [talhao.cultura, `${numero(talhao.area_ha)} ha`].filter(Boolean).join(' · ') }}
          </p>
        </div>
        <template v-if="sessao.podeGerir">
          <button
            type="button"
            class="rounded-md px-2 py-1 text-sm font-medium text-campo-700 transition-colors hover:bg-campo-50 pointer-coarse:min-h-11"
            :aria-label="`Alterar ${talhao.nome}`"
            @click="abrir(talhao)"
          >
            Alterar
          </button>
          <button
            type="button"
            class="rounded-md px-2 py-1 text-sm font-medium text-red-700 transition-colors hover:bg-red-50 pointer-coarse:min-h-11"
            :aria-label="`Remover ${talhao.nome}`"
            @click="emRemocao = talhao"
          >
            Remover
          </button>
        </template>
      </div>

      <!-- A carência primeiro: colher antes é proibido, e o erro não tem conserto. -->
      <p
        v-if="talhao.em_carencia"
        class="mt-3 flex gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-800"
        data-teste="carencia"
      >
        <IconeSvg
          nome="urgente"
          class="mt-0.5 h-4 w-4 shrink-0 text-red-600"
        />
        <span>{{ talhao.alertas[0]?.justificativa }}</span>
      </p>
      <p
        v-else
        class="mt-3 flex items-center gap-2 text-sm text-stone-600"
      >
        <IconeSvg
          nome="confirmado"
          class="h-4 w-4 shrink-0 text-campo-500"
        />
        {{ talhao.colheita_liberada_em === null
          ? 'Nada com carência aplicado aqui.'
          : `Colheita liberada desde ${dataBr(talhao.colheita_liberada_em)}.` }}
      </p>

      <dl class="mt-3 grid grid-cols-2 gap-3 border-t border-stone-100 pt-3 text-sm">
        <div>
          <dt class="text-xs text-stone-500">
            Custo aplicado
          </dt>
          <dd class="font-semibold text-stone-900 tabular-nums">
            {{ talhao.custo_total === null ? '—' : reais(talhao.custo_total) }}
          </dd>
        </div>
        <div>
          <dt class="text-xs text-stone-500">
            Por hectare
          </dt>
          <dd class="font-semibold text-stone-900 tabular-nums">
            {{ talhao.custo_por_ha === null ? '—' : reais(talhao.custo_por_ha) }}
          </dd>
        </div>
      </dl>
    </li>
  </ul>

  <ConfirmarRemocao
    v-if="emRemocao"
    titulo="Remover talhão"
    :texto="`Remover ${emRemocao.nome}? Só dá para remover um talhão sem aplicações.`"
    :remover="() => talhoes.remover(emRemocao!.id)"
    @fechar="emRemocao = null"
  />
</template>
