<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import CartaoDeAlerta from '@/components/CartaoDeAlerta.vue'
import CoberturaDoEstoque from '@/components/CoberturaDoEstoque.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
import IconeSvg from '@/components/IconeSvg.vue'
import NumeroRolante from '@/components/NumeroRolante.vue'
import { URL_DO_RELATORIO } from '@/services/estoque'
import { useEstoqueStore } from '@/stores/estoque'
import type { Gravidade, Reposicao } from '@/types/api'

// Só exibe: quem decide alerta, justificativa, reposição e limitação é o backend.
const estoque = useEstoqueStore()
onMounted(() => estoque.carregar())

const hoje = new Date()
const dataDeHoje = hoje.toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' })

const contagem = computed(() => {
  const total: Record<Gravidade, number> = { alta: 0, media: 0, baixa: 0 }
  for (const { alerta } of estoque.alertas) total[alerta.gravidade]++
  return total
})

const GRAVIDADES = [
  { gravidade: 'alta', marca: 'bg-urgente', rotulo: (n: number) => (n === 1 ? 'urgente' : 'urgentes') },
  {
    gravidade: 'media',
    marca: 'bg-atencao-forte',
    rotulo: (n: number) => (n === 1 ? 'pede atenção' : 'pedem atenção'),
  },
  { gravidade: 'baixa', marca: 'bg-observar', rotulo: () => 'para observar' },
] as const

// A frase de abertura: o que importa hoje, com os nomes.
const lista = new Intl.ListFormat('pt-BR', { style: 'long', type: 'conjunction' })
const resumoDoDia = computed(() => {
  const urgentes = [
    ...new Set(estoque.alertas.filter((a) => a.alerta.gravidade === 'alta').map((a) => a.insumo.nome)),
  ]
  const { media, baixa } = contagem.value
  if (urgentes.length) {
    return `${lista.format(urgentes)} ${urgentes.length === 1 ? 'precisa' : 'precisam'} de ação hoje.`
  }
  if (media) return `Nada urgente hoje. ${media} ${media === 1 ? 'ponto pede' : 'pontos pedem'} atenção.`
  if (baixa) return 'Nada urgente hoje. Há pontos para observar.'
  return 'Estoque em ordem: nenhum alerta hoje.'
})

// Os números filtram a lista: um clique mostra só aquela gravidade, outro desfaz.
const filtro = ref<Gravidade | null>(null)
const alertasVisiveis = computed(() =>
  filtro.value ? estoque.alertas.filter((a) => a.alerta.gravidade === filtro.value) : estoque.alertas,
)
const filtrar = (gravidade: Gravidade) => (filtro.value = filtro.value === gravidade ? null : gravidade)

// Datas AAAA-MM-DD comparam certo como texto.
const reposicoes = computed(() =>
  estoque.insumos
    .flatMap((insumo) => (insumo.analise.reposicao ? [{ insumo, ...insumo.analise.reposicao }] : []))
    .sort((a, b) => a.pedir_em.localeCompare(b.pedir_em)),
)

const dataBr = (data: string) => data.split('-').reverse().join('/')
const quando = (r: Reposicao) => (r.pedir_hoje ? 'pedir hoje' : `pedir até ${dataBr(r.pedir_em)}`)

// O pedido à revenda costuma sair pelo WhatsApp: a lista vai pronta, em texto, com o que
// é para agora separado do que pode esperar (a quantidade destes vale para a data dada).
const listaDeCompras = computed(() => {
  const item = (r: (typeof reposicoes.value)[number]) =>
    `- ${r.insumo.nome}: ${r.quantidade.toLocaleString('pt-BR')} ${r.insumo.unidade}`
  const agora = reposicoes.value.filter((r) => r.pedir_hoje)
  const depois = reposicoes.value.filter((r) => !r.pedir_hoje)
  return [
    `Lista de compras (CampoCerto, ${hoje.toLocaleDateString('pt-BR')})`,
    ...(agora.length ? ['', 'Pedir agora:', ...agora.map(item)] : []),
    ...(depois.length
      ? ['', 'Próximos pedidos:', ...depois.map((r) => `${item(r)} até ${dataBr(r.pedir_em)}`)]
      : []),
  ].join('\n')
})
const linkWhatsApp = computed(() => `https://wa.me/?text=${encodeURIComponent(listaDeCompras.value)}`)
// A área de transferência só existe em HTTPS ou localhost; fora disso, fica o WhatsApp.
const podeCopiar = typeof navigator !== 'undefined' && Boolean(navigator.clipboard)
const rotuloDaCopia = { copiada: 'Lista copiada', falhou: 'Não deu para copiar' } as const
const copia = ref<keyof typeof rotuloDaCopia | null>(null)
async function copiar() {
  try {
    await navigator.clipboard.writeText(listaDeCompras.value)
    copia.value = 'copiada'
  } catch {
    // Permissão negada pelo navegador: o link do WhatsApp continua ao lado.
    copia.value = 'falhou'
  }
  setTimeout(() => (copia.value = null), 2500)
}
</script>

<template>
  <CabecalhoDePagina
    titulo="Painel"
    :sobretitulo="dataDeHoje"
  >
    <template
      v-if="estoque.insumos.length"
      #acoes
    >
      <a
        :href="URL_DO_RELATORIO"
        download
        class="botao-secundario"
        data-teste="relatorio"
      >
        <IconeSvg
          nome="baixar"
          class="size-4 text-tinta-3"
        />
        Baixar relatório (Excel)
      </a>
    </template>
  </CabecalhoDePagina>

  <p
    v-if="estoque.erro"
    role="alert"
    class="border-l-2 border-urgente pl-3 text-sm text-urgente"
  >
    {{ estoque.erro }}
  </p>

  <!-- A forma da página enquanto os dados chegam: nada salta quando chegam. -->
  <div
    v-else-if="!estoque.carregado"
    aria-busy="true"
    aria-label="Carregando o painel"
  >
    <div class="esqueleto h-9 w-full max-w-xl" />
    <div class="mt-8 grid grid-cols-3 border-y border-linha">
      <div
        v-for="n in 3"
        :key="n"
        class="px-5 py-5"
      >
        <div class="esqueleto h-11 w-14" />
        <div class="esqueleto mt-3 h-4 w-24" />
      </div>
    </div>
    <div class="esqueleto mt-12 h-72" />
  </div>

  <EstadoVazio
    v-else-if="!estoque.insumos.length"
    icone="folha"
    titulo="Nenhum insumo cadastrado ainda"
    texto="Cadastre os insumos e lance as compras e retiradas. Os alertas aparecem aqui, cada um com a conta que o justifica."
  >
    <RouterLink
      :to="{ name: 'insumos' }"
      class="botao-primario"
    >
      Cadastrar insumos
    </RouterLink>
    <RouterLink
      :to="{ name: 'importar' }"
      class="botao-texto"
    >
      Importar uma planilha
    </RouterLink>
  </EstadoVazio>

  <template v-else>
    <p
      class="max-w-3xl animate-surgir font-serif text-[1.625rem] leading-snug tracking-[-0.01em] text-tinta sm:text-[1.875rem]"
      data-teste="resumo-do-dia"
    >
      {{ resumoDoDia }}
    </p>

    <div
      class="mt-8 grid grid-cols-3 border-y border-linha"
      role="group"
      aria-label="Filtrar os alertas por gravidade"
    >
      <button
        v-for="item in GRAVIDADES"
        :key="item.gravidade"
        type="button"
        class="relative px-3 py-5 text-left transition-colors duration-150 not-first:border-l not-first:border-linha hover:bg-folha/70 disabled:pointer-events-none sm:px-5"
        :aria-pressed="filtro === item.gravidade"
        :disabled="!contagem[item.gravidade]"
        @click="filtrar(item.gravidade)"
      >
        <span
          class="block font-serif text-[2.5rem] leading-none sm:text-5xl"
          :class="contagem[item.gravidade] ? 'text-tinta' : 'text-linha-forte'"
        >
          <NumeroRolante :valor="contagem[item.gravidade]" />
        </span>
        <span class="mt-3 flex items-center gap-1.5 text-sm text-tinta-2">
          <span
            class="size-[7px] shrink-0 rounded-[2px]"
            :class="item.marca"
            aria-hidden="true"
          />
          {{ item.rotulo(contagem[item.gravidade]) }}
        </span>
        <!-- O filtro ativo ganha um traço embaixo, que cresce da esquerda. -->
        <span
          class="absolute inset-x-0 -bottom-px h-0.5 origin-left transition-transform duration-300 ease-chegar"
          :class="[item.marca, filtro === item.gravidade ? 'scale-x-100' : 'scale-x-0']"
          aria-hidden="true"
        />
      </button>
    </div>

    <div class="mt-12 grid gap-12 lg:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
      <section aria-labelledby="titulo-alertas">
        <div class="flex items-baseline justify-between gap-3">
          <h2
            id="titulo-alertas"
            class="titulo-secao"
          >
            Alertas
            <span class="ml-1 font-sans text-sm font-normal text-tinta-3 tabular-nums">{{ alertasVisiveis.length }}</span>
          </h2>
          <button
            v-if="filtro"
            type="button"
            class="botao-texto -mr-2 px-2 py-1 text-xs"
            @click="filtro = null"
          >
            Mostrar todos
          </button>
        </div>
        <p
          v-if="!estoque.alertas.length"
          class="mt-4 border-y border-linha py-6 text-sm text-tinta-2"
        >
          Nenhum alerta hoje. Os insumos estão dentro do esperado para o consumo registrado.
        </p>
        <TransitionGroup
          v-else
          tag="ul"
          name="lista"
          appear
          class="relative mt-4 divide-y divide-linha border-y border-linha"
        >
          <CartaoDeAlerta
            v-for="({ insumo, alerta }, indice) in alertasVisiveis"
            :key="`${insumo.id}-${alerta.tipo}-${alerta.justificativa}`"
            :alerta="alerta"
            :insumo="insumo"
            :style="{ '--i': indice }"
          />
        </TransitionGroup>
      </section>

      <CoberturaDoEstoque
        :insumos="estoque.insumos"
        class="animate-surgir [animation-delay:80ms]"
      />
    </div>

    <section
      v-if="reposicoes.length"
      aria-labelledby="titulo-reposicao"
      class="mt-14"
    >
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2
            id="titulo-reposicao"
            class="titulo-secao"
          >
            Reposição
          </h2>
          <p class="mt-1 text-sm text-tinta-3">
            Quantidade sugerida e data limite do pedido.
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <button
            v-if="podeCopiar"
            type="button"
            class="botao-texto"
            aria-live="polite"
            @click="copiar"
          >
            <IconeSvg
              :nome="copia === 'copiada' ? 'confirmado' : 'copiar'"
              class="size-4"
            />
            {{ copia ? rotuloDaCopia[copia] : 'Copiar lista' }}
          </button>
          <a
            :href="linkWhatsApp"
            target="_blank"
            rel="noopener"
            class="botao-primario"
            data-teste="whatsapp"
          >
            <IconeSvg
              nome="enviar"
              class="size-4"
            />
            Enviar pelo WhatsApp
          </a>
        </div>
      </div>
      <ul class="mt-5 divide-y divide-linha border-y border-linha">
        <li
          v-for="item in reposicoes"
          :key="item.insumo.id"
          class="grid gap-x-8 gap-y-1.5 py-4 sm:grid-cols-[13rem_minmax(0,1fr)]"
          data-teste="reposicao"
        >
          <div>
            <RouterLink
              :to="{ name: 'insumo', params: { id: item.insumo.id } }"
              class="text-sm text-tinta-2 transition-colors duration-150 hover:text-campo-700"
            >
              {{ item.insumo.nome }}
            </RouterLink>
            <p class="mt-0.5 font-serif text-2xl leading-tight text-tinta tabular-nums">
              {{ item.quantidade.toLocaleString('pt-BR') }}
              <span class="font-sans text-sm text-tinta-3">{{ item.insumo.unidade }}</span>
            </p>
          </div>
          <div class="min-w-0">
            <p
              class="text-sm font-medium"
              :class="item.pedir_hoje ? 'text-urgente' : 'text-tinta'"
            >
              {{ quando(item) }}
            </p>
            <p class="mt-0.5 text-sm leading-relaxed text-tinta-2">
              {{ item.justificativa }}
            </p>
          </div>
        </li>
      </ul>
    </section>

    <section
      aria-labelledby="titulo-limitacoes"
      class="mt-14"
    >
      <h2
        id="titulo-limitacoes"
        class="titulo-secao"
      >
        Limitações da análise
      </h2>
      <p class="mt-1 text-sm text-tinta-3">
        O que a conta não considera, por insumo.
      </p>
      <div class="mt-5 divide-y divide-linha border-y border-linha">
        <details
          v-for="insumo in estoque.insumos"
          :key="insumo.id"
          class="group"
        >
          <summary class="flex cursor-pointer list-none items-center justify-between gap-3 py-3 text-sm text-tinta transition-colors duration-150 hover:text-campo-700 [&::-webkit-details-marker]:hidden">
            <span>
              {{ insumo.nome }}
              <span class="ml-1 text-tinta-3 tabular-nums">{{ insumo.analise.limitacoes.length }}</span>
            </span>
            <IconeSvg
              nome="seta"
              class="size-4 text-tinta-3 transition-transform duration-200 ease-mover group-open:rotate-90"
            />
          </summary>
          <ul class="animate-surgir list-disc space-y-1 pb-4 pl-5 text-sm leading-relaxed text-tinta-2">
            <li
              v-for="limitacao in insumo.analise.limitacoes"
              :key="limitacao"
            >
              {{ limitacao }}
            </li>
          </ul>
        </details>
      </div>
    </section>
  </template>
</template>
