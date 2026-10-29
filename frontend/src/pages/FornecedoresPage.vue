<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, useTemplateRef } from 'vue'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import ConfirmarRemocao from '@/components/ConfirmarRemocao.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
import { mensagemDeErro } from '@/stores/estoque'
import { useFornecedoresStore } from '@/stores/fornecedores'
import { useSessaoStore } from '@/stores/sessao'
import type { Fornecedor } from '@/types/api'

const fornecedores = useFornecedoresStore()
const sessao = useSessaoStore()
onMounted(() => fornecedores.carregar())

// Os ativos primeiro: são os que se escolhem no pedido. O desativado fica pelo histórico.
const ordenados = computed(() =>
  [...fornecedores.fornecedores].sort((a, b) => Number(b.ativo) - Number(a.ativo)),
)

const vazio = { nome: '', contato: '', telefone: '', cidade: '', observacao: '', ativo: true }
const form = reactive({ ...vazio })
const aberto = ref(false)
const editandoId = ref<number>()
const salvando = ref(false)
const erroDoForm = ref<string | null>(null)
const tituloDoForm = useTemplateRef<HTMLElement>('tituloDoForm')
const emRemocao = ref<Fornecedor | null>(null)

function abrir(fornecedor?: Fornecedor) {
  Object.assign(
    form,
    fornecedor
      ? {
          nome: fornecedor.nome,
          contato: fornecedor.contato ?? '',
          telefone: fornecedor.telefone ?? '',
          cidade: fornecedor.cidade ?? '',
          observacao: fornecedor.observacao ?? '',
          ativo: fornecedor.ativo,
        }
      : vazio,
  )
  editandoId.value = fornecedor?.id
  erroDoForm.value = null
  aberto.value = true
  nextTick(() => tituloDoForm.value?.focus())
}

async function salvar() {
  salvando.value = true
  erroDoForm.value = null
  try {
    // Campo apagado vai como null: fornecedor sem telefone, e não telefone "".
    await fornecedores.salvar(
      {
        nome: form.nome,
        contato: form.contato || null,
        telefone: form.telefone || null,
        cidade: form.cidade || null,
        observacao: form.observacao || null,
        ativo: form.ativo,
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

/** O link do WhatsApp: só os dígitos, com o 55 do Brasil quando o número vem sem ele. */
function whatsapp(telefone: string): string | null {
  const digitos = telefone.replace(/\D/g, '')
  if (digitos.length < 10) return null
  return `https://wa.me/${digitos.length <= 11 ? `55${digitos}` : digitos}`
}
</script>

<template>
  <CabecalhoDePagina
    titulo="Fornecedores"
    descricao="As revendas de onde vêm os insumos. O preço pago a cada uma fica guardado, para comparar na próxima compra."
  >
    <template #acoes>
      <RouterLink
        :to="{ name: 'compras' }"
        class="botao-secundario"
      >
        Pedidos de compra
      </RouterLink>
      <button
        v-if="fornecedores.fornecedores.length && sessao.podeGerir"
        type="button"
        class="botao-primario"
        @click="abrir()"
      >
        Novo fornecedor
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
      {{ editandoId === undefined ? 'Novo fornecedor' : 'Alterar fornecedor' }}
    </h2>
    <label class="flutuante">
      <input
        v-model="form.nome"
        required
        maxlength="120"
        placeholder="Agropecuária Ariquemes"
        class="campo"
      >
      <span class="rotulo">Nome</span>
    </label>
    <label class="flutuante">
      <input
        v-model="form.contato"
        maxlength="120"
        placeholder="Seu Antônio"
        class="campo"
      >
      <span class="rotulo">Contato <span class="font-normal text-stone-500">(opcional)</span></span>
    </label>
    <label class="flutuante">
      <input
        v-model="form.telefone"
        type="tel"
        inputmode="tel"
        maxlength="30"
        placeholder="(69) 99999-0000"
        class="campo"
      >
      <span class="rotulo">WhatsApp <span class="font-normal text-stone-500">(opcional)</span></span>
    </label>
    <label class="flutuante">
      <input
        v-model="form.cidade"
        maxlength="80"
        placeholder="Ariquemes"
        class="campo"
      >
      <span class="rotulo">Cidade <span class="font-normal text-stone-500">(opcional)</span></span>
    </label>
    <label class="flutuante sm:col-span-2 lg:col-span-3">
      <input
        v-model="form.observacao"
        maxlength="500"
        placeholder="Entrega às terças; prazo de 30 dias no boleto"
        class="campo"
      >
      <span class="rotulo">Observação <span class="font-normal text-stone-500">(opcional)</span></span>
    </label>
    <label
      v-if="editandoId !== undefined"
      class="flex min-h-11 items-center gap-2 text-sm text-stone-700"
    >
      <input
        v-model="form.ativo"
        type="checkbox"
        class="h-4 w-4 accent-campo-600"
      >
      Ativo (aparece no pedido e na compra)
    </label>
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
    v-if="fornecedores.erro"
    role="alert"
    class="mt-6 text-sm text-red-700"
  >
    {{ fornecedores.erro }}
  </p>

  <EstadoVazio
    v-else-if="fornecedores.carregado && !fornecedores.fornecedores.length && !aberto"
    icone="loja"
    titulo="Nenhum fornecedor cadastrado"
    :texto="sessao.podeGerir
      ? 'Cadastre as revendas. Ao lançar uma compra, diga de quem foi: a sugestão de pedido já sai separada por revenda, com o último preço.'
      : 'Quando o dono da fazenda cadastrar as revendas, as compras e os pedidos mostram de quem vieram.'"
  >
    <button
      v-if="sessao.podeGerir"
      type="button"
      class="botao-primario"
      @click="abrir()"
    >
      Cadastrar fornecedor
    </button>
  </EstadoVazio>

  <ul
    v-else-if="fornecedores.fornecedores.length"
    class="grid animate-surgir gap-3 md:grid-cols-2"
  >
    <li
      v-for="fornecedor in ordenados"
      :key="fornecedor.id"
      class="cartao flex flex-col gap-2 p-4"
      :class="fornecedor.ativo ? '' : 'opacity-70'"
      data-teste="fornecedor"
    >
      <div class="flex items-start gap-2">
        <div class="min-w-0 flex-1">
          <RouterLink
            :to="{ name: 'fornecedor', params: { id: fornecedor.id } }"
            class="font-semibold text-stone-900 hover:text-campo-700 hover:underline"
          >
            {{ fornecedor.nome }}
          </RouterLink>
          <p class="text-sm text-stone-500">
            {{ [fornecedor.contato, fornecedor.cidade].filter(Boolean).join(' · ') || 'Sem contato cadastrado' }}
          </p>
        </div>
        <span
          v-if="!fornecedor.ativo"
          class="rounded-full bg-stone-100 px-2 py-0.5 text-xs font-semibold text-stone-600"
        >Desativado</span>
        <template v-if="sessao.podeGerir">
          <button
            type="button"
            class="rounded-md px-2 py-1 text-sm font-medium text-campo-700 transition-colors hover:bg-campo-50 pointer-coarse:min-h-11"
            :aria-label="`Alterar ${fornecedor.nome}`"
            @click="abrir(fornecedor)"
          >
            Alterar
          </button>
          <button
            type="button"
            class="rounded-md px-2 py-1 text-sm font-medium text-red-700 transition-colors hover:bg-red-50 pointer-coarse:min-h-11"
            :aria-label="`Remover ${fornecedor.nome}`"
            @click="emRemocao = fornecedor"
          >
            Remover
          </button>
        </template>
      </div>
      <p
        v-if="fornecedor.observacao"
        class="text-sm text-stone-600"
      >
        {{ fornecedor.observacao }}
      </p>
      <a
        v-if="fornecedor.telefone && whatsapp(fornecedor.telefone)"
        :href="whatsapp(fornecedor.telefone)!"
        target="_blank"
        rel="noopener"
        class="inline-flex w-fit items-center gap-1.5 text-sm font-medium text-campo-700 hover:underline"
      >
        WhatsApp {{ fornecedor.telefone }}
      </a>
      <p
        v-else-if="fornecedor.telefone"
        class="text-sm text-stone-600"
      >
        {{ fornecedor.telefone }}
      </p>
    </li>
  </ul>

  <ConfirmarRemocao
    v-if="emRemocao"
    titulo="Remover fornecedor"
    :texto="`Remover ${emRemocao.nome}? Só dá para remover quem foi cadastrado por engano, sem compra nem pedido. Com histórico, desative em Alterar.`"
    :remover="() => fornecedores.remover(emRemocao!.id)"
    @fechar="emRemocao = null"
  />
</template>
