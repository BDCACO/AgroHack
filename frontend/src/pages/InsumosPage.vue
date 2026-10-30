<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
import GerenciarCategorias from '@/components/GerenciarCategorias.vue'
import IconeSvg from '@/components/IconeSvg.vue'
import JanelaModal from '@/components/JanelaModal.vue'
import SeloDeGravidade from '@/components/SeloDeGravidade.vue'
import { dataBr, reais } from '@/formatos'
import { useCategoriasStore } from '@/stores/categorias'
import { mensagemDeErro, useEstoqueStore } from '@/stores/estoque'
import { useSessaoStore } from '@/stores/sessao'
import type { Gravidade, Insumo } from '@/types/api'

const estoque = useEstoqueStore()
const sessao = useSessaoStore()
const categorias = useCategoriasStore()
onMounted(() => Promise.all([estoque.carregar(), categorias.carregar()]))
const gerenciandoCategorias = ref(false)

// Os filtros ficam no navegador: a lista inteira já veio (uma fazenda tem dezenas de
// insumos, não milhares) e filtrar aqui responde a cada letra digitada.
const filtro = reactive({
  busca: '',
  categoria: '' as number | '' | 'sem',
  situacao: '' as Gravidade | 'sem' | '',
})
/** Como a API compara na busca: sem maiúsculas nem acentos ("ureia" acha "Uréia"). */
const comoSeBusca = (texto: string) =>
  texto.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase().trim()
const filtrados = computed(() => {
  const busca = comoSeBusca(filtro.busca)
  return estoque.insumos.filter((insumo) => {
    if (busca && !comoSeBusca(insumo.nome).includes(busca)) return false
    if (filtro.categoria === 'sem' && insumo.categoria_id) return false
    if (typeof filtro.categoria === 'number' && insumo.categoria_id !== filtro.categoria) return false
    const pior = insumo.analise.alertas[0]?.gravidade
    if (filtro.situacao === 'sem' && pior) return false
    if (filtro.situacao && filtro.situacao !== 'sem' && pior !== filtro.situacao) return false
    return true
  })
})
const filtrando = computed(() => Boolean(filtro.busca || filtro.categoria !== '' || filtro.situacao))
const limparFiltros = () => Object.assign(filtro, { busca: '', categoria: '', situacao: '' })

// Input numérico vazio vale '' no v-model; '' = "não informado" (null na API).
const vazio = {
  nome: '',
  unidade: '',
  estoque_minimo: '' as number | '',
  prazo: '' as number | '',
  embalagem: '' as number | '',
  pedido_minimo: '' as number | '',
  carencia: '' as number | '',
  categoria: '' as number | '',
  marcas: '',
  codigoDeBarras: '',
}
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
          embalagem: insumo.embalagem ?? '',
          pedido_minimo: insumo.pedido_minimo ?? '',
          carencia: insumo.carencia_dias ?? '',
          categoria: insumo.categoria_id ?? '',
          marcas: insumo.marcas_preferenciais ?? '',
          codigoDeBarras: insumo.codigo_de_barras ?? '',
        }
      : vazio,
  )
  editandoId.value = insumo?.id
  erroDoForm.value = null
  // Numa janela, e não no alto da página: quem tocou em "Alterar" lá embaixo da lista não perde
  // o lugar, e ao fechar o foco volta para o botão.
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
        embalagem: form.embalagem === '' ? null : form.embalagem,
        pedido_minimo: form.pedido_minimo === '' ? null : form.pedido_minimo,
        carencia_dias: form.carencia === '' ? null : form.carencia,
        categoria_id: form.categoria === '' ? null : form.categoria,
        marcas_preferenciais: form.marcas.trim() === '' ? null : form.marcas.trim(),
        codigo_de_barras: form.codigoDeBarras.trim() === '' ? null : form.codigoDeBarras.trim(),
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
  >
    <template #acoes>
      <button
        v-if="sessao.podeGerir"
        type="button"
        class="botao-secundario"
        @click="gerenciandoCategorias = true"
      >
        Categorias
      </button>
      <button
        v-if="estoque.insumos.length && sessao.podeGerir"
        type="button"
        class="botao-primario"
        @click="abrir()"
      >
        Novo insumo
      </button>
    </template>
  </CabecalhoDePagina>

  <JanelaModal
    v-if="aberto"
    :titulo="editandoId === undefined ? 'Novo insumo' : 'Alterar insumo'"
    larga
    @fechar="aberto = false"
  >
    <form
      class="grid gap-4 sm:grid-cols-2"
      data-teste="form-insumo"
      @submit.prevent="salvar"
    >
      <label class="flutuante">
        <input
          v-model="form.nome"
          autofocus
          required
          maxlength="120"
          placeholder="Ureia agrícola"
          class="campo"
        >
        <span class="rotulo">Nome</span>
      </label>
      <label class="flutuante">
        <input
          v-model="form.unidade"
          required
          maxlength="20"
          list="unidades"
          placeholder="kg"
          class="campo"
        >
        <span class="rotulo">Unidade</span>
        <datalist id="unidades">
          <option value="kg" />
          <option value="L" />
          <option value="t" />
          <option value="sc" />
          <option value="dose" />
          <option value="un" />
        </datalist>
      </label>
      <label class="flutuante">
        <input
          v-model.number="form.estoque_minimo"
          type="number"
          min="0"
          step="any"
          placeholder=" "
          class="campo"
        >
        <span class="rotulo">Estoque mínimo <span class="font-normal text-stone-500">(opcional)</span></span>
      </label>
      <label class="flutuante">
        <input
          v-model.number="form.prazo"
          type="number"
          min="0"
          max="365"
          step="1"
          placeholder=" "
          class="campo"
        >
        <span class="rotulo">Prazo de entrega, em dias <span class="font-normal text-stone-500">(opcional)</span></span>
      </label>
      <label class="flutuante">
        <input
          v-model.number="form.embalagem"
          type="number"
          min="0.001"
          step="any"
          placeholder="50"
          class="campo"
        >
        <span class="rotulo">Embalagem, em {{ form.unidade || 'unidades' }} <span class="font-normal text-stone-500">(opcional)</span></span>
      </label>
      <label class="flutuante">
        <input
          v-model.number="form.pedido_minimo"
          type="number"
          min="0"
          step="any"
          placeholder=" "
          class="campo"
        >
        <span class="rotulo">Pedido mínimo, em {{ form.unidade || 'unidades' }} <span class="font-normal text-stone-500">(opcional)</span></span>
      </label>
      <label class="flutuante">
        <input
          v-model.number="form.carencia"
          type="number"
          min="0"
          max="365"
          step="1"
          placeholder=" "
          class="campo"
        >
        <span class="rotulo">Carência, em dias <span class="font-normal text-stone-500">(defensivos)</span></span>
      </label>
      <label class="flutuante">
        <select
          v-model.number="form.categoria"
          class="campo"
          data-teste="categoria"
        >
          <option value="">
            Sem categoria
          </option>
          <option
            v-for="categoria in categorias.categorias"
            :key="categoria.id"
            :value="categoria.id"
          >
            {{ categoria.nome }}
          </option>
        </select>
        <span class="rotulo">Categoria</span>
      </label>
      <label class="flutuante sm:col-span-2">
        <input
          v-model="form.marcas"
          type="text"
          maxlength="200"
          placeholder=" "
          class="campo"
        >
        <span class="rotulo">Marcas ou especificações de preferência <span class="font-normal text-stone-500">(opcional)</span></span>
      </label>
      <label class="flutuante sm:col-span-2">
        <input
          v-model="form.codigoDeBarras"
          type="text"
          maxlength="64"
          placeholder=" "
          class="campo"
        >
        <span class="rotulo">Código de barras ou QR Code <span class="font-normal text-stone-500">(lido pelo app; apague o campo e salve para remover)</span></span>
      </label>
      <p class="text-xs text-stone-500 sm:col-span-2">
        O mínimo dispara o alerta de estoque baixo e vira margem de segurança na reposição. O prazo
        é quanto o fornecedor leva para entregar; sem ele, a análise assume 15 dias e avisa. Com a
        embalagem (50 para o saco de 50 kg) e o pedido mínimo da revenda, a reposição sai em
        embalagens fechadas. O preço entra ao lançar cada compra, em Movimentações. A carência é
        quantos dias depois de aplicar se pode colher ou abater (está na bula ou no receituário);
        0 se não tem, como a ureia. Com ela, os talhões avisam até quando não colher. As marcas
        preferenciais vão na mensagem de cotação, para a revenda saber o que pode mandar.
      </p>
      <p
        v-if="erroDoForm"
        role="alert"
        class="text-sm text-red-700 sm:col-span-2"
      >
        {{ erroDoForm }}
      </p>
      <div class="flex flex-col-reverse gap-2 sm:col-span-2 sm:flex-row sm:justify-end">
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
    v-if="estoque.erro"
    role="alert"
    class="mt-6 text-sm text-red-700"
  >
    {{ estoque.erro }}
  </p>

  <EstadoVazio
    v-else-if="estoque.carregado && !estoque.insumos.length"
    icone="insumos"
    titulo="Nenhum insumo cadastrado"
    :texto="sessao.podeGerir
      ? 'Cadastre os produtos que você guarda no galpão: adubos, defensivos, sementes, sal mineral, vacinas…'
      : 'O dono da fazenda cadastra os insumos; depois, é só lançar as retiradas.'"
  >
    <button
      v-if="sessao.podeGerir"
      type="button"
      class="botao-primario"
      @click="abrir()"
    >
      Cadastrar insumo
    </button>
  </EstadoVazio>

  <template v-else-if="estoque.insumos.length">
    <div
      class="mb-3 grid gap-3 sm:grid-cols-[2fr_1fr_1fr]"
      role="search"
      aria-label="Filtrar insumos"
    >
      <label class="flutuante">
        <input
          v-model="filtro.busca"
          type="search"
          placeholder="ureia"
          class="campo"
          data-teste="busca"
        >
        <span class="rotulo">Buscar pelo nome</span>
      </label>
      <label class="flutuante">
        <select
          v-model="filtro.categoria"
          class="campo"
          data-teste="filtro-categoria"
        >
          <option value="">
            Todas
          </option>
          <option
            v-for="categoria in categorias.categorias"
            :key="categoria.id"
            :value="categoria.id"
          >
            {{ categoria.nome }}
          </option>
          <option value="sem">
            Sem categoria
          </option>
        </select>
        <span class="rotulo">Categoria</span>
      </label>
      <label class="flutuante">
        <select
          v-model="filtro.situacao"
          class="campo"
          data-teste="filtro-situacao"
        >
          <option value="">
            Todas
          </option>
          <option value="alta">
            Urgente
          </option>
          <option value="media">
            Atenção
          </option>
          <option value="baixa">
            Observar
          </option>
          <option value="sem">
            Sem alertas
          </option>
        </select>
        <span class="rotulo">Situação</span>
      </label>
    </div>
    <p
      v-if="filtrando"
      class="mb-3 flex flex-wrap items-center gap-2 text-sm text-stone-600"
      role="status"
      data-teste="contagem"
    >
      {{ filtrados.length === 1 ? '1 insumo' : `${filtrados.length} insumos` }} de {{ estoque.insumos.length }}
      <button
        type="button"
        class="botao-texto px-2 py-0.5"
        @click="limparFiltros"
      >
        Limpar filtros
      </button>
    </p>

    <!-- No celular, um cartão por insumo no lugar da tabela, que não cabe sem rolar para o
     lado. Tocar no insumo abre a página dele; "Alterar" fica à mão do polegar. -->
    <ul class="cartao animate-surgir divide-y divide-stone-100 md:hidden">
      <li
        v-for="insumo in filtrados"
        :key="insumo.id"
        class="relative flex items-center gap-2 py-3 pr-2 pl-4 transition-colors active:bg-stone-50"
        data-teste="insumo-celular"
      >
        <div class="min-w-0 flex-1">
          <RouterLink
            :to="{ name: 'insumo', params: { id: insumo.id } }"
            class="block font-semibold text-stone-900 after:absolute after:inset-0 after:content-[''] focus-visible:outline-none [&:focus-visible]:after:ring-2 [&:focus-visible]:after:ring-campo-600 [&:focus-visible]:after:ring-inset"
          >
            {{ insumo.nome }}
          </RouterLink>
          <p class="mt-0.5 text-sm text-stone-600">
            <span
              class="font-semibold tabular-nums"
              :class="insumo.estoque_atual < 0 ? 'text-red-700' : 'text-stone-800'"
            >{{ numero(insumo.estoque_atual) }} {{ insumo.unidade }}</span>
            em estoque<template v-if="insumo.valor_em_estoque !== null">
              · {{ reais(insumo.valor_em_estoque) }}
            </template>
          </p>
          <p
            v-if="insumo.em_pedido"
            class="mt-0.5 text-xs font-medium text-sky-800"
          >
            + {{ numero(insumo.em_pedido) }} {{ insumo.unidade }} a caminho<template v-if="insumo.chegada_prevista">
              , até {{ dataBr(insumo.chegada_prevista) }}
            </template>
          </p>
          <p class="mt-0.5 text-xs text-stone-500 tabular-nums">
            Mínimo {{ insumo.estoque_minimo === null ? 'não definido' : `${numero(insumo.estoque_minimo)} ${insumo.unidade}` }}
            · entrega {{ insumo.prazo_reposicao_dias === null ? 'sem prazo' : `em ${insumo.prazo_reposicao_dias} dias` }}
          </p>
          <div class="mt-2">
            <SeloDeGravidade :gravidade="insumo.analise.alertas[0]?.gravidade ?? null" />
          </div>
        </div>
        <button
          v-if="sessao.podeGerir"
          type="button"
          class="relative z-10 min-h-11 rounded-lg px-3 text-sm font-medium text-campo-700 transition-colors active:bg-campo-50"
          :aria-label="`Alterar ${insumo.nome}`"
          @click="abrir(insumo)"
        >
          Alterar
        </button>
        <IconeSvg
          nome="seta"
          class="h-5 w-5 shrink-0 text-stone-300"
        />
      </li>
    </ul>

    <div class="cartao hidden animate-surgir overflow-x-auto md:block">
      <table class="w-full text-left text-sm">
        <thead class="bg-stone-50/80 text-xs tracking-wide text-stone-500 uppercase">
          <tr>
            <th class="px-3 py-3 xl:px-4 font-semibold">
              Insumo
            </th>
            <th class="px-3 py-3 xl:px-4 text-right font-semibold">
              Estoque atual
            </th>
            <th class="px-3 py-3 xl:px-4 text-right font-semibold">
              Valor em estoque
            </th>
            <th class="px-3 py-3 xl:px-4 text-right font-semibold">
              Mínimo
            </th>
            <th class="px-3 py-3 xl:px-4 text-right font-semibold">
              Prazo
            </th>
            <th class="px-3 py-3 xl:px-4 font-semibold">
              Situação
            </th>
            <th class="px-3 py-3 xl:px-4">
              <span class="sr-only">Ações</span>
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-stone-100">
          <tr
            v-for="insumo in filtrados"
            :key="insumo.id"
            class="transition-colors hover:bg-stone-50/70"
          >
            <td class="px-3 py-3 xl:px-4 font-medium text-stone-800">
              <RouterLink
                :to="{ name: 'insumo', params: { id: insumo.id } }"
                class="hover:text-campo-700 hover:underline"
              >
                {{ insumo.nome }}
              </RouterLink>
              <span
                v-if="insumo.categoria"
                class="block text-xs font-normal text-stone-500"
              >{{ insumo.categoria }}</span>
            </td>
            <td
              class="px-3 py-3 xl:px-4 text-right whitespace-nowrap tabular-nums"
              :class="insumo.estoque_atual < 0 ? 'text-red-700' : ''"
            >
              {{ numero(insumo.estoque_atual) }} {{ insumo.unidade }}
              <!-- Pedido à revenda e ainda não chegou: a reposição já desconta. -->
              <span
                v-if="insumo.em_pedido"
                class="block text-xs font-medium text-sky-800"
                :title="insumo.chegada_prevista ? `Chega até ${dataBr(insumo.chegada_prevista)}` : undefined"
              >+ {{ numero(insumo.em_pedido) }} a caminho</span>
            </td>
            <!-- Sem compra com preço, não há custo médio: um traço, e não R$ 0,00. -->
            <td
              class="px-3 py-3 xl:px-4 text-right whitespace-nowrap tabular-nums text-stone-600"
              :title="insumo.custo_medio === null ? undefined : `Custo médio: ${reais(insumo.custo_medio)}/${insumo.unidade}`"
            >
              {{ insumo.valor_em_estoque === null ? '—' : reais(insumo.valor_em_estoque) }}
            </td>
            <td class="px-3 py-3 xl:px-4 text-right whitespace-nowrap tabular-nums text-stone-600">
              {{ insumo.estoque_minimo === null ? '—' : `${numero(insumo.estoque_minimo)} ${insumo.unidade}` }}
            </td>
            <td class="px-3 py-3 xl:px-4 text-right whitespace-nowrap tabular-nums text-stone-600">
              {{ insumo.prazo_reposicao_dias === null ? '—' : `${insumo.prazo_reposicao_dias} dias` }}
            </td>
            <td class="px-3 py-3 xl:px-4">
              <!-- A API já ordena os alertas do mais grave para o mais leve. -->
              <SeloDeGravidade :gravidade="insumo.analise.alertas[0]?.gravidade ?? null" />
            </td>
            <td class="px-3 py-3 xl:px-4 text-right">
              <button
                v-if="sessao.podeGerir"
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
    <p
      v-if="filtrando && !filtrados.length"
      class="mt-3 text-sm text-stone-500"
    >
      Nenhum insumo com esses filtros.
    </p>
  </template>

  <GerenciarCategorias
    v-if="gerenciandoCategorias"
    @fechar="gerenciandoCategorias = false"
  />
</template>
