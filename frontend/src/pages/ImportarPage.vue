<script setup lang="ts">
import { ref } from 'vue'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import { mensagemDeErro, useEstoqueStore } from '@/stores/estoque'
import type { ResultadoImportacao } from '@/types/api'

// Só coleta e mostra: quem confere a planilha e decide o que é erro é a API.
const estoque = useEstoqueStore()

const nomeDoArquivo = ref('')
const conteudo = ref('')
const previa = ref<ResultadoImportacao | null>(null)
const importado = ref<ResultadoImportacao | null>(null)
const ocupado = ref(false)
const erro = ref<string | null>(null)
// O confirmar falhou sem resposta: o servidor pode ter gravado mesmo assim.
const confirmacaoIncerta = ref(false)

// O limite da API (5 MB de texto). Conferir antes poupa enviar o arquivo à toa.
const TAMANHO_MAXIMO = 5_000_000

async function lerArquivo(arquivo: File): Promise<string> {
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
  if (/\.xlsx?$/i.test(arquivo.name)) {
    erro.value = 'Este é um arquivo do Excel. Abra no Excel e use Arquivo → Salvar como → CSV.'
  } else if (arquivo.size > TAMANHO_MAXIMO) {
    erro.value = 'Arquivo maior que 5 MB. Divida a planilha em partes e importe uma de cada vez.'
  } else {
    await enviar(await lerArquivo(arquivo), false)
  }
}

async function enviar(texto: string, confirmar: boolean) {
  ocupado.value = true
  erro.value = null
  confirmacaoIncerta.value = false
  try {
    const resultado = await estoque.importarPlanilha(texto, confirmar)
    conteudo.value = texto
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

const colunas = [
  ['data', 'DD/MM/AAAA, como o Excel grava.'],
  ['insumo', 'Nome do produto. Se já estiver cadastrado, a linha entra nele.'],
  ['unidade', 'kg, L, sc, t… Obrigatória só para insumo que ainda não existe.'],
  ['tipo', 'entrada (compra que chegou) ou saída (retirada do galpão).'],
  ['quantidade', 'Maior que zero, com vírgula nos decimais: 25,5.'],
  ['validade', 'Opcional, só em entradas: a validade do lote.'],
] as const

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
        Uma linha por movimentação, com estas colunas na primeira linha:
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
      <p class="mt-4 text-sm text-stone-600">
        No Excel: <em>Arquivo → Salvar como → CSV</em>.
      </p>
      <a
        href="/modelo-movimentacoes.csv"
        download
        class="mt-3 inline-flex rounded-md border border-campo-600 px-4 py-2 text-sm font-medium text-campo-700 hover:bg-campo-50"
      >
        Baixar planilha modelo
      </a>
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
      <label
        class="flex cursor-pointer flex-col items-center rounded-lg border-2 border-dashed border-stone-300 bg-white px-4 py-8 text-center hover:border-campo-600"
        :class="ocupado ? 'pointer-events-none opacity-60' : ''"
      >
        <span class="font-medium text-campo-700">
          {{ ocupado ? 'Conferindo…' : 'Escolher arquivo CSV' }}
        </span>
        <span class="mt-1 text-sm text-stone-500">
          {{ nomeDoArquivo || 'Nada é gravado antes de você conferir o resumo.' }}
        </span>
        <input
          type="file"
          accept=".csv,text/csv"
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
            @click="enviar(conteudo, false)"
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
          @click="enviar(conteudo, true)"
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
