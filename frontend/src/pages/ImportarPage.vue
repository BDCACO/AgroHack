<script setup lang="ts">
import { computed, ref } from 'vue'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import IconeSvg from '@/components/IconeSvg.vue'
import BotaoDeDownload from '@/components/BotaoDeDownload.vue'
import { baixarPlanilhaModelo } from '@/services/estoque'
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
  if (arquivo) await processar(arquivo)
}

// Arrastar a planilha da pasta direto para a área: o caminho mais curto no computador.
const arrastando = ref(false)
async function soltar(evento: DragEvent) {
  arrastando.value = false
  const arquivo = evento.dataTransfer?.files[0]
  if (arquivo && !ocupado.value) await processar(arquivo)
}

async function processar(arquivo: File) {
  nomeDoArquivo.value = arquivo.name
  importado.value = null
  previa.value = null
  erro.value = null
  confirmacaoIncerta.value = false // o aviso era do arquivo anterior
  const extensao = arquivo.name.toLowerCase().split('.').pop() ?? ''
  try {
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
  } catch {
    // O navegador não conseguiu ler o arquivo (apagado, movido, sem permissão).
    erro.value = 'Não deu para ler o arquivo. Escolha-o de novo.'
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

function importarRepetida() {
  const ok = window.confirm(
    'Todas as linhas desta planilha já estão no sistema. Importar de novo duplica cada entrada e saída. Continuar?',
  )
  if (ok) reenviar(true)
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
      class="cartao animate-surgir p-5 lg:col-span-2"
    >
      <h2
        id="titulo-modelo"
        class="text-base font-semibold text-stone-900"
      >
        Como montar a planilha
      </h2>
      <p class="mt-1 text-sm text-stone-600">
        Baixe a planilha modelo: ela já vem formatada, com listas de escolha, a lista dos seus
        insumos e um exemplo preenchido. Uma linha por movimentação.
      </p>
      <div class="mt-4">
        <BotaoDeDownload
          rotulo="Baixar planilha modelo (Excel)"
          :baixar="baixarPlanilhaModelo"
          class="botao-primario"
          data-teste="modelo-xlsx"
        />
      </div>
      <p class="mt-4 text-sm text-stone-600">
        As colunas, na primeira linha:
      </p>
      <dl class="mt-3 space-y-2 text-sm">
        <div
          v-for="[coluna, explicacao] in colunas"
          :key="coluna"
        >
          <dt class="inline-block rounded bg-campo-50 px-1.5 font-mono text-xs font-semibold text-campo-700">
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

    <!-- No celular, escolher o arquivo vem antes da explicação: quem já tem a planilha não
         precisa rolar até o fim. -->
    <section
      aria-labelledby="titulo-arquivo"
      class="max-lg:order-first lg:col-span-3"
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
      <!-- Enquanto um arquivo passa por cima, a área se acende e o ícone sobe: "solte
           aqui". Os filhos ignoram o ponteiro nessa hora; senão o dragleave dispara ao
           passar por cima deles e a área pisca. -->
      <label
        class="group relative flex animate-surgir cursor-pointer flex-col items-center overflow-hidden rounded-xl border-2 border-dashed px-4 py-10 text-center transition duration-200 ease-chegada [animation-delay:80ms] has-[:focus-visible]:border-campo-600 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-campo-600/30"
        :class="[
          arrastando
            ? 'scale-[1.01] border-campo-600 bg-campo-50 [&_*]:pointer-events-none'
            : 'border-stone-300 bg-white hover:border-campo-500 hover:bg-campo-50/50',
          ocupado ? 'pointer-events-none' : '',
        ]"
        data-teste="area-de-soltar"
        @dragenter.prevent="arrastando = true"
        @dragover.prevent="arrastando = true"
        @dragleave="arrastando = false"
        @drop.prevent="soltar"
      >
        <span
          class="flex h-14 w-14 items-center justify-center rounded-full bg-campo-100 text-campo-700 transition duration-200 ease-chegada"
          :class="arrastando ? '-translate-y-1.5 scale-110 bg-campo-600 text-white' : 'group-hover:-translate-y-0.5'"
          aria-hidden="true"
        >
          <IconeSvg
            nome="importar"
            class="h-7 w-7"
          />
        </span>
        <span class="mt-3 font-semibold text-campo-800">
          <template v-if="ocupado">Conferindo…</template>
          <template v-else-if="arrastando">Solte para conferir</template>
          <!-- Em tela de toque não há o que arrastar. -->
          <template v-else>Escolha <span class="pointer-coarse:hidden">ou arraste </span>a planilha</template>
        </span>
        <span class="mt-1 text-sm text-stone-500">
          {{ nomeDoArquivo || '.xlsx ou .csv · nada é gravado antes de você conferir o resumo' }}
        </span>
        <!-- Barra de "trabalhando" enquanto a API confere: o pedido está andando. -->
        <span
          v-if="ocupado"
          class="absolute inset-x-0 bottom-0 h-1 overflow-hidden bg-campo-100"
          aria-hidden="true"
        >
          <span class="block h-full w-1/3 animate-vaivem rounded-full bg-campo-500" />
        </span>
        <input
          type="file"
          accept=".xlsx,.xlsm,.csv,.txt,.xls,.ods,.numbers"
          class="sr-only"
          data-teste="arquivo"
          @change="escolher"
        >
      </label>

      <Transition name="surgir">
        <div
          v-if="erro"
          role="alert"
          class="cartao mt-4 border-red-200 bg-red-50 p-4 text-sm text-red-800"
        >
          <p>{{ erro }}</p>
          <template v-if="confirmacaoIncerta">
            <p class="mt-1">
              Não dá para saber se a importação foi gravada. Confira de novo antes de importar: a
              conferência avisa se as linhas já estão no sistema.
            </p>
            <button
              type="button"
              class="botao-secundario mt-3"
              data-teste="conferir-de-novo"
              @click="reenviar(false)"
            >
              Conferir de novo
            </button>
          </template>
        </div>
      </Transition>

      <Transition
        name="surgir"
        mode="out-in"
      >
        <div
          v-if="previa?.erros.length"
          role="alert"
          class="cartao mt-4 border-red-200 bg-red-50 p-5"
          data-teste="erros"
        >
          <p class="flex items-center gap-2 font-semibold text-red-800">
            <IconeSvg
              nome="urgente"
              class="h-5 w-5 shrink-0"
            />
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
          class="cartao mt-4 p-5"
          data-teste="previa"
        >
          <p class="font-semibold text-stone-900">
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
                      class="ml-1 rounded-full bg-campo-100 px-2 py-0.5 text-xs font-semibold text-campo-700"
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
            class="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"
            data-teste="ja-lancadas"
          >
            {{ contar(previa.ja_lancadas, 'linha é igual', 'linhas são iguais') }} a movimentações já
            lançadas.
            Se esta planilha já foi importada, importar de novo duplica o consumo.
          </p>
          <!-- Tudo já lançado: é a mesma planilha (ou a cópia de segurança) de novo. Importar
             seria dobrar o consumo, então o botão principal não convida a isso. -->
          <button
            v-if="previa.ja_lancadas === previa.linhas"
            type="button"
            class="botao-perigo mt-4"
            :disabled="ocupado"
            data-teste="importar-mesmo-assim"
            @click="importarRepetida"
          >
            Importar mesmo assim (duplica tudo)
          </button>
          <button
            v-else
            type="button"
            class="botao-primario mt-4"
            :disabled="ocupado"
            @click="reenviar(true)"
          >
            {{ ocupado ? 'Importando…' : `Importar ${contar(previa.linhas, 'movimentação', 'movimentações')}` }}
          </button>
        </div>
      </Transition>

      <Transition name="surgir">
        <div
          v-if="importado"
          role="status"
          class="cartao mt-4 flex gap-4 border-campo-200 bg-campo-50 p-5"
          data-teste="importado"
        >
          <!-- O sinal de concluído se desenha: o círculo, depois a marca. -->
          <svg
            viewBox="0 0 52 52"
            class="h-12 w-12 shrink-0 text-campo-600"
            aria-hidden="true"
          >
            <circle
              cx="26"
              cy="26"
              r="23"
              fill="none"
              stroke="currentColor"
              stroke-width="3"
              class="animate-tracar-circulo [stroke-dasharray:145] [stroke-dashoffset:145]"
            />
            <path
              d="M16 27l7 7 14-15"
              fill="none"
              stroke="currentColor"
              stroke-width="3.5"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="animate-tracar-marca [stroke-dasharray:34] [stroke-dashoffset:34]"
            />
          </svg>
          <div>
            <p class="font-semibold text-campo-900">
              Importação concluída: {{ contar(importado.linhas, 'movimentação', 'movimentações') }}.
            </p>
            <p class="mt-0.5 text-sm text-campo-800">
              O estoque e os alertas já foram recalculados.
            </p>
            <div class="mt-3 flex flex-wrap gap-2">
              <RouterLink
                :to="{ name: 'painel' }"
                class="botao-primario"
              >
                Ver os alertas
              </RouterLink>
              <RouterLink
                v-if="importado.insumos.some((insumo) => insumo.novo)"
                :to="{ name: 'insumos' }"
                class="botao-texto"
              >
                Completar os insumos novos
              </RouterLink>
            </div>
          </div>
        </div>
      </Transition>
    </section>
  </div>
</template>
