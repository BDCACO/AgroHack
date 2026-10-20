<script setup lang="ts">
import { computed, ref } from 'vue'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import { URL_DA_PLANILHA_MODELO } from '@/services/estoque'
import { mensagemDeErro, useEstoqueStore } from '@/stores/estoque'
import type { PlanilhaParaImportar, ResultadoImportacao } from '@/types/api'

// Só coleta e mostra: quem confere a planilha e decide o que é erro é a API.
const estoque = useEstoqueStore()

const nomeDoArquivo = ref('')
const planilha = ref<PlanilhaParaImportar | null>(null)
const previa = ref<ResultadoImportacao | null>(null)
const importado = ref<ResultadoImportacao | null>(null)
const ocupado = ref(false)
const erro = ref<string | null>(null)
// O confirmar falhou sem resposta: o servidor pode ter gravado mesmo assim.
const confirmacaoIncerta = ref(false)

// O limite da API (5 MB). Conferir antes poupa enviar o arquivo à toa.
const TAMANHO_MAXIMO = 5_000_000

/** O .xlsx vai inteiro, em base64, para a API ler. */
function lerXlsx(arquivo: File): Promise<string> {
  return new Promise((pronto, falhou) => {
    const leitor = new FileReader()
    // "data:<tipo>;base64,<conteúdo>" → só o conteúdo.
    leitor.onload = () => pronto(String(leitor.result).split(',')[1] ?? '')
    leitor.onerror = () => falhou(leitor.error)
    leitor.readAsDataURL(arquivo)
  })
}

async function lerCsv(arquivo: File): Promise<string> {
  const bytes = await arquivo.arrayBuffer()
  try {
    return new TextDecoder('utf-8', { fatal: true }).decode(bytes)
  } catch {
    // O "CSV (separado por vírgulas)" do Excel em português sai em Windows-1252,
    // não em UTF-8: sem isto, "agrícola" chegaria como "agr�cola".
    return new TextDecoder('windows-1252').decode(bytes)
  }
}

async function escolher(evento: Event) {
  const campo = evento.target as HTMLInputElement
  const arquivo = campo.files?.[0]
  // Limpa o campo: escolher o mesmo arquivo de novo (depois de corrigi-lo) dispara o change.
  campo.value = ''
  if (!arquivo) return
  nomeDoArquivo.value = arquivo.name
  importado.value = null
  previa.value = null
  const extensao = arquivo.name.toLowerCase().split('.').pop() ?? ''
  if (extensao in OUTROS_FORMATOS) {
    erro.value = OUTROS_FORMATOS[extensao]!
  } else if (arquivo.size > TAMANHO_MAXIMO) {
    erro.value = 'Arquivo maior que 5 MB. Divida a planilha em partes e importe uma de cada vez.'
  } else if (extensao === 'xlsx' || extensao === 'xlsm') {
    await enviar({ xlsx: await lerXlsx(arquivo) }, false)
  } else if (extensao === 'csv' || extensao === 'txt') {
    await enviar({ conteudo: await lerCsv(arquivo) }, false)
  } else {
    erro.value = 'Formato não reconhecido. Use a planilha do Excel (.xlsx) ou um CSV.'
  }
}

// Planilhas que a API não lê, cada uma com o caminho para virar .xlsx.
const OUTROS_FORMATOS: Record<string, string> = {
  xls: 'Arquivo do Excel antigo (.xls). Abra no Excel e salve como Pasta de Trabalho do Excel (.xlsx).',
  ods: 'Planilha do LibreOffice (.ods). Abra no LibreOffice e salve como Excel 2007-365 (.xlsx).',
  numbers: 'Planilha do Numbers. Use Arquivo → Exportar para → Excel (.xlsx).',
}

async function enviar(arquivo: PlanilhaParaImportar, confirmar: boolean) {
  ocupado.value = true
  erro.value = null
  confirmacaoIncerta.value = false
  try {
    const resultado = await estoque.importarPlanilha(arquivo, confirmar)
    planilha.value = arquivo
    previa.value = resultado.importado ? null : resultado
    importado.value = resultado.importado ? resultado : null
  } catch (falha) {
    erro.value = mensagemDeErro(falha)
    if (confirmar) {
      // Não oferece o mesmo botão de novo: se o servidor gravou, importaria tudo duas
      // vezes. Conferir de novo mostra se as linhas já estão lá (`ja_lancadas`).
      previa.value = null
      confirmacaoIncerta.value = true
    }
  } finally {
    ocupado.value = false
  }
}

/** Com a planilha já conferida: `confirmar` grava; sem, confere de novo. */
function reenviar(confirmar: boolean) {
  if (planilha.value) enviar(planilha.value, confirmar)
}

const colunas = [
  ['data', 'Dia da compra ou da retirada, DD/MM/AAAA. Não pode ser futura.'],
  ['insumo', 'Nome do produto. Se já estiver cadastrado, a linha entra nele; se não, é cadastrado.'],
  ['unidade', 'kg, L, t, sc, dose… Obrigatória só para insumo novo.'],
  ['tipo', 'entrada (compra que chegou) ou saída (retirada do galpão).'],
  ['quantidade', 'Maior que zero. Decimais com vírgula: 25,5.'],
  ['validade', 'Opcional, só em entradas: a validade do lote.'],
] as const

// O resultado aparece sem trocar de página: o leitor de tela precisa ouvir que chegou. Os
// erros têm role="alert" e a importação concluída, role="status"; aqui, o resto.
const anuncio = computed(() => {
  if (ocupado.value) return 'Conferindo a planilha…'
  if (previa.value && !previa.value.erros.length) {
    return `Planilha conferida: ${contar(previa.value.linhas, 'movimentação', 'movimentações')}. Confira o resumo e importe.`
  }
  return ''
})

const contar = (total: number, singular: string, plural: string) =>
  `${total.toLocaleString('pt-BR')} ${total === 1 ? singular : plural}`
const dataBr = (data: string | null) => data?.split('-').reverse().join('/')
const quantidade = (valor: number, unidade: string) =>
  valor ? `${valor.toLocaleString('pt-BR', { maximumFractionDigits: 3 })} ${unidade}` : '—'
</script>

<template>
  <CabecalhoDePagina
    titulo="Importar dados"
    descricao="Carregar de uma vez o histórico de compras e retiradas que já está numa planilha."
  />

  <div class="mt-6 grid gap-6 lg:grid-cols-5">
    <section
      aria-labelledby="titulo-modelo"
      class="rounded-lg border border-stone-200 bg-white p-4 lg:col-span-2"
    >
      <h2
        id="titulo-modelo"
        class="font-semibold text-stone-800"
      >
        Como montar a planilha
      </h2>
      <p class="mt-1 text-sm text-stone-600">
        Baixe a planilha modelo: ela já vem formatada, com listas de escolha, a lista dos seus
        insumos e um exemplo preenchido. Uma linha por movimentação.
      </p>
      <a
        :href="URL_DA_PLANILHA_MODELO"
        download
        class="mt-3 inline-flex rounded-md bg-campo-600 px-4 py-2 text-sm font-medium text-white hover:bg-campo-700"
        data-teste="modelo-xlsx"
      >
        Baixar planilha modelo (Excel)
      </a>
      <p class="mt-4 text-sm text-stone-600">
        As colunas, na primeira linha:
      </p>
      <dl class="mt-3 space-y-2 text-sm">
        <div
          v-for="[coluna, explicacao] in colunas"
          :key="coluna"
        >
          <dt class="font-mono text-xs font-semibold text-campo-700">
            {{ coluna }}
          </dt>
          <dd class="text-stone-600">
            {{ explicacao }}
          </dd>
        </div>
      </dl>
      <p class="mt-4 text-sm text-stone-500">
        Também vale um CSV com as mesmas colunas, separado por ponto e vírgula —
        <a
          href="/modelo-movimentacoes.csv"
          download
          class="font-medium text-campo-700 underline hover:text-campo-900"
        >modelo em CSV</a>.
      </p>
    </section>

    <section
      aria-labelledby="titulo-arquivo"
      class="lg:col-span-3"
    >
      <h2
        id="titulo-arquivo"
        class="sr-only"
      >
        Arquivo
      </h2>
      <p
        class="sr-only"
        role="status"
      >
        {{ anuncio }}
      </p>
      <label
        class="flex cursor-pointer flex-col items-center rounded-lg border-2 border-dashed border-stone-300 bg-white px-4 py-8 text-center hover:border-campo-600 has-[:focus-visible]:border-campo-600 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-campo-600/30"
        :class="ocupado ? 'pointer-events-none opacity-60' : ''"
      >
        <span class="font-medium text-campo-700">
          {{ ocupado ? 'Conferindo…' : 'Escolher a planilha (.xlsx ou .csv)' }}
        </span>
        <span class="mt-1 text-sm text-stone-500">
          {{ nomeDoArquivo || 'Nada é gravado antes de você conferir o resumo.' }}
        </span>
        <input
          type="file"
          accept=".xlsx,.xlsm,.csv,.txt,.xls,.ods,.numbers"
          class="sr-only"
          data-teste="arquivo"
          @change="escolher"
        >
      </label>

      <div
        v-if="erro"
        role="alert"
        class="mt-4 text-sm text-red-700"
      >
        <p>{{ erro }}</p>
        <template v-if="confirmacaoIncerta">
          <p class="mt-1">
            Não dá para saber se a importação foi gravada. Confira de novo antes de importar: a
            conferência avisa se as linhas já estão no sistema.
          </p>
          <button
            type="button"
            class="mt-2 rounded-md border border-campo-600 px-4 py-2 font-medium text-campo-700 hover:bg-campo-50"
            data-teste="conferir-de-novo"
            @click="reenviar(false)"
          >
            Conferir de novo
          </button>
        </template>
      </div>

      <div
        v-if="previa?.erros.length"
        role="alert"
        class="mt-4 rounded-lg border border-red-200 bg-red-50 p-4"
        data-teste="erros"
      >
        <p class="font-medium text-red-800">
          Nada foi importado. Corrija na planilha e escolha o arquivo de novo:
        </p>
        <ul class="mt-2 max-h-64 list-disc space-y-1 overflow-y-auto pl-5 text-sm text-red-800">
          <li
            v-for="mensagem in previa.erros"
            :key="mensagem"
          >
            {{ mensagem }}
          </li>
        </ul>
      </div>

      <div
        v-else-if="previa"
        class="mt-4 rounded-lg border border-stone-200 bg-white p-4"
        data-teste="previa"
      >
        <p class="font-medium text-stone-800">
          {{ contar(previa.linhas, 'movimentação', 'movimentações') }}:
          {{ contar(previa.entradas, 'entrada', 'entradas') }} e
          {{ contar(previa.saidas, 'saída', 'saídas') }}, de {{ dataBr(previa.primeira_data) }} a
          {{ dataBr(previa.ultima_data) }}.
        </p>
        <!-- Os totais são o que denuncia um número lido errado (mil virando um). -->
        <div class="mt-3 overflow-x-auto">
          <table class="w-full text-left text-sm">
            <caption class="sr-only">
              Total por insumo
            </caption>
            <thead class="text-xs uppercase tracking-wide text-stone-500">
              <tr>
                <th class="py-1 pr-4 font-semibold">
                  Insumo
                </th>
                <th class="py-1 pr-4 text-right font-semibold">
                  Entra
                </th>
                <th class="py-1 text-right font-semibold">
                  Sai
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-stone-100">
              <tr
                v-for="insumo in previa.insumos"
                :key="insumo.nome"
                data-teste="total-insumo"
              >
                <td class="py-1.5 pr-4 text-stone-800">
                  {{ insumo.nome }}
                  <span
                    v-if="insumo.novo"
                    class="ml-1 rounded-full bg-campo-100 px-2 py-0.5 text-xs font-medium text-campo-700"
                  >novo</span>
                </td>
                <td class="py-1.5 pr-4 text-right tabular-nums">
                  {{ quantidade(insumo.entradas, insumo.unidade) }}
                </td>
                <td class="py-1.5 text-right tabular-nums">
                  {{ quantidade(insumo.saidas, insumo.unidade) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p
          v-if="previa.insumos.some((insumo) => insumo.novo)"
          class="mt-2 text-sm text-stone-600"
        >
          Os insumos novos serão cadastrados. Depois, complete o mínimo e o prazo de entrega deles
          na tela de Insumos.
        </p>
        <p
          v-if="previa.ja_lancadas"
          class="mt-3 rounded-md bg-amber-50 p-3 text-sm text-amber-900"
          data-teste="ja-lancadas"
        >
          {{ contar(previa.ja_lancadas, 'linha é igual', 'linhas são iguais') }} a movimentações já
          lançadas.
          Se esta planilha já foi importada, importar de novo duplica o consumo.
        </p>
        <button
          type="button"
          class="mt-4 rounded-md bg-campo-600 px-4 py-2 text-sm font-medium text-white hover:bg-campo-700 disabled:opacity-50"
          :disabled="ocupado"
          @click="reenviar(true)"
        >
          {{ ocupado ? 'Importando…' : `Importar ${contar(previa.linhas, 'movimentação', 'movimentações')}` }}
        </button>
      </div>

      <div
        v-if="importado"
        role="status"
        class="mt-4 rounded-lg border border-campo-100 bg-campo-50 p-4"
        data-teste="importado"
      >
        <p class="font-medium text-campo-900">
          Importação concluída: {{ contar(importado.linhas, 'movimentação', 'movimentações') }}.
        </p>
        <div class="mt-3 flex flex-wrap gap-2">
          <RouterLink
            :to="{ name: 'painel' }"
            class="rounded-md bg-campo-600 px-4 py-2 text-sm font-medium text-white hover:bg-campo-700"
          >
            Ver os alertas
          </RouterLink>
          <RouterLink
            v-if="importado.insumos.some((insumo) => insumo.novo)"
            :to="{ name: 'insumos' }"
            class="rounded-md px-4 py-2 text-sm font-medium text-campo-700 hover:bg-campo-100"
          >
            Completar os insumos novos
          </RouterLink>
        </div>
      </div>
    </section>
  </div>
</template>
