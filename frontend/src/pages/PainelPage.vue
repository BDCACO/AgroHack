<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import CartaoDeAlerta from '@/components/CartaoDeAlerta.vue'
import CoberturaDoEstoque from '@/components/CoberturaDoEstoque.vue'
import NumeroRolante from '@/components/NumeroRolante.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
import IconeSvg, { type NomeIcone } from '@/components/IconeSvg.vue'
import { reais } from '@/formatos'
import { URL_DO_RELATORIO } from '@/services/estoque'
import { useEstoqueStore } from '@/stores/estoque'
import type { Gravidade, Reposicao } from '@/types/api'

// Só exibe: quem decide alerta, justificativa, reposição e limitação é o backend.
const estoque = useEstoqueStore()
onMounted(() => Promise.all([estoque.carregar(), estoque.carregarResumo()]))

const hoje = new Date()
const dataDeHoje = hoje.toLocaleDateString('pt-BR', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
})

const GRAVIDADES: {
  gravidade: Gravidade
  titulo: string
  dica: string
  icone: NomeIcone
  cor: { faixa: string; texto: string; icone: string; anel: string }
}[] = [
  {
    gravidade: 'alta',
    titulo: 'Urgentes',
    dica: 'resolver hoje',
    icone: 'urgente',
    cor: { faixa: 'bg-red-500', texto: 'text-red-700', icone: 'bg-red-50 text-red-600', anel: 'ring-red-500' },
  },
  {
    gravidade: 'media',
    titulo: 'Atenção',
    dica: 'nos próximos dias',
    icone: 'relogio',
    cor: { faixa: 'bg-amber-400', texto: 'text-amber-800', icone: 'bg-amber-50 text-amber-600', anel: 'ring-amber-400' },
  },
  {
    gravidade: 'baixa',
    titulo: 'Observar',
    dica: 'com calma',
    icone: 'olho',
    cor: { faixa: 'bg-sky-400', texto: 'text-sky-800', icone: 'bg-sky-50 text-sky-600', anel: 'ring-sky-400' },
  },
]

const contagem = computed(() => {
  const total: Record<Gravidade, number> = { alta: 0, media: 0, baixa: 0 }
  for (const { alerta } of estoque.alertas) total[alerta.gravidade]++
  return total
})

// A frase do dia: o que o produtor precisa saber antes de rolar a página.
const resumoDoDia = computed(() => {
  const urgentes = [
    ...new Set(
      estoque.alertas.filter((a) => a.alerta.gravidade === 'alta').map((a) => a.insumo.nome),
    ),
  ]
  const { media, baixa } = contagem.value
  if (urgentes.length) {
    const quem = urgentes.length === 1 ? 'insumo precisa' : 'insumos precisam'
    return `${urgentes.length} ${quem} de ação hoje: ${urgentes.join(', ')}.`
  }
  if (media) return `Nada urgente hoje; ${media} ${media === 1 ? 'ponto pede' : 'pontos pedem'} atenção nos próximos dias.`
  if (baixa) return 'Tudo em dia. Há pontos para observar com calma.'
  return 'Tudo em dia: nenhum alerta no estoque.'
})

// Os cartões de gravidade filtram a lista: um clique mostra só os urgentes, outro desfaz.
const filtro = ref<Gravidade | null>(null)
const alertasVisiveis = computed(() =>
  filtro.value ? estoque.alertas.filter((a) => a.alerta.gravidade === filtro.value) : estoque.alertas,
)
const filtrar = (gravidade: Gravidade) =>
  (filtro.value = filtro.value === gravidade ? null : gravidade)
const tituloDoFiltro = computed(() => GRAVIDADES.find((g) => g.gravidade === filtro.value)?.titulo)

// Datas AAAA-MM-DD comparam certo como texto.
const reposicoes = computed(() =>
  estoque.insumos
    .flatMap((insumo) => (insumo.analise.reposicao ? [{ insumo, ...insumo.analise.reposicao }] : []))
    .sort((a, b) => a.pedir_em.localeCompare(b.pedir_em)),
)

// O estoque em reais, do GET /resumo. Um número só por cartão, e embaixo o que ele quer
// dizer; sem preço nenhum, o cartão diz o que falta em vez de mostrar R$ 0,00.
const cartoesEmReais = computed(() => {
  const resumo = estoque.resumo
  if (!resumo) return []
  const { compras_sugeridas: compras, perdas } = resumo
  const pedidos = compras.pedidos === 1 ? '1 pedido' : `${compras.pedidos} pedidos`
  return [
    {
      titulo: 'Valor em estoque',
      valor: resumo.valor_em_estoque === null ? '—' : reais(resumo.valor_em_estoque),
      nota:
        resumo.valor_em_estoque === null
          ? 'lance o preço nas compras'
          : 'pelo custo médio das compras',
    },
    {
      titulo: 'Compras, próximos 30 dias',
      valor: compras.valor === null ? '—' : reais(compras.valor),
      nota: !compras.pedidos
        ? 'nada a pedir'
        : compras.pedir_hoje
          ? `${pedidos}, ${compras.pedir_hoje} para hoje`
          : pedidos,
    },
    {
      titulo: 'Perdas, últimos 30 dias',
      valor: reais(perdas.ultimos_30_dias),
      nota: `descartes e faltas · ${reais(perdas.total)} no total`,
    },
  ]
})

const dataBr = (data: string) => data.split('-').reverse().join('/')
const quando = (r: Reposicao) => (r.pedir_hoje ? 'pedir hoje' : `pedir até ${dataBr(r.pedir_em)}`)

// O pedido à revenda costuma sair pelo WhatsApp: a lista vai pronta, em texto. O que é
// para pedir já vem separado do que ainda dá para esperar — a quantidade destes vale
// para a data indicada, não para hoje.
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
    :descricao="estoque.insumos.length ? resumoDoDia : 'Alertas sobre o estoque de insumos, com a justificativa de cada um.'"
  >
    <template
      v-if="estoque.insumos.length"
      #acoes
    >
      <!-- Link de download comum: o arquivo vem pronto da API. -->
      <a
        :href="URL_DO_RELATORIO"
        download
        class="botao-secundario"
        data-teste="relatorio"
      >
        <IconeSvg
          nome="baixar"
          class="h-4 w-4"
        />
        Baixar relatório (Excel)
      </a>
    </template>
  </CabecalhoDePagina>

  <p
    v-if="estoque.erro"
    role="alert"
    class="cartao border-red-200 bg-red-50 p-4 text-sm text-red-800"
  >
    {{ estoque.erro }}
  </p>

  <!-- Esqueleto: a forma da página enquanto os dados chegam, sem salto quando chegam. -->
  <div
    v-else-if="!estoque.carregado"
    aria-busy="true"
    aria-label="Carregando o painel"
  >
    <div class="grid grid-cols-3 gap-3">
      <div
        v-for="n in 3"
        :key="n"
        class="esqueleto h-28 rounded-xl"
      />
    </div>
    <div class="esqueleto mt-6 h-56 rounded-xl" />
    <div
      v-for="n in 3"
      :key="n"
      class="esqueleto mt-3 h-20 rounded-xl"
    />
  </div>

  <EstadoVazio
    v-else-if="!estoque.insumos.length"
    icone="folha"
    titulo="Nenhum insumo cadastrado ainda"
    texto="Cadastre os insumos e lance as compras e retiradas: os alertas aparecem aqui, cada um com a conta que o justifica."
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
      ou importar uma planilha
    </RouterLink>
  </EstadoVazio>

  <template v-else>
    <div
      class="grid grid-cols-3 gap-3"
      role="group"
      aria-label="Filtrar os alertas por gravidade"
    >
      <button
        v-for="(item, indice) in GRAVIDADES"
        :key="item.gravidade"
        type="button"
        class="cartao group relative animate-surgir overflow-hidden p-3 text-left transition-[translate,scale,box-shadow] duration-200 ease-chegada hover:-translate-y-0.5 hover:shadow-md active:scale-[0.98] active:duration-100 disabled:pointer-events-none sm:p-4"
        :class="filtro === item.gravidade ? ['ring-2 ring-offset-2', item.cor.anel] : ''"
        :style="{ animationDelay: `${indice * 60}ms` }"
        :aria-pressed="filtro === item.gravidade"
        :disabled="!contagem[item.gravidade]"
        @click="filtrar(item.gravidade)"
      >
        <span
          class="absolute inset-x-0 top-0 h-1"
          :class="item.cor.faixa"
          aria-hidden="true"
        />
        <span class="flex items-center justify-between gap-2">
          <span
            class="text-xs font-semibold sm:text-sm"
            :class="item.cor.texto"
          >{{ item.titulo }}</span>
          <span
            class="hidden rounded-lg p-1.5 transition-transform duration-150 ease-chegada group-hover:scale-110 sm:block"
            :class="item.cor.icone"
            aria-hidden="true"
          >
            <IconeSvg
              :nome="item.icone"
              class="h-4 w-4"
            />
          </span>
        </span>
        <span
          class="mt-1 block text-3xl font-bold text-stone-900 sm:mt-2 sm:text-4xl"
          :class="contagem[item.gravidade] ? '' : 'text-stone-300'"
        >
          <NumeroRolante :valor="contagem[item.gravidade]" />
        </span>
        <span class="mt-0.5 hidden text-xs text-stone-500 sm:block">{{ item.dica }}</span>
      </button>
    </div>

    <section
      v-if="estoque.resumo"
      aria-label="O estoque em reais"
      class="mt-3 animate-surgir [animation-delay:100ms]"
      data-teste="em-reais"
    >
      <dl class="grid gap-3 sm:grid-cols-3">
        <div
          v-for="cartao in cartoesEmReais"
          :key="cartao.titulo"
          class="cartao px-4 py-3"
        >
          <dt class="text-xs font-semibold text-stone-500">
            {{ cartao.titulo }}
          </dt>
          <dd class="mt-1 text-xl font-bold text-stone-900 tabular-nums">
            {{ cartao.valor }}
          </dd>
          <dd class="text-xs text-stone-500">
            {{ cartao.nota }}
          </dd>
        </div>
      </dl>
      <!-- O que os números em reais não contam (insumo sem preço, por exemplo). -->
      <p
        v-for="limitacao in estoque.resumo.limitacoes"
        :key="limitacao"
        class="mt-2 text-xs text-stone-500"
      >
        {{ limitacao }}
      </p>
    </section>

    <CoberturaDoEstoque
      :insumos="estoque.insumos"
      class="mt-6 animate-surgir [animation-delay:150ms]"
    />

    <section
      aria-labelledby="titulo-alertas"
      class="mt-8"
    >
      <div class="flex flex-wrap items-baseline justify-between gap-2">
        <h2
          id="titulo-alertas"
          class="text-base font-semibold text-stone-900"
        >
          Alertas
          <span class="ml-1 text-sm font-normal text-stone-500 tabular-nums">{{ alertasVisiveis.length }}</span>
        </h2>
        <button
          v-if="filtro"
          type="button"
          class="botao-texto px-2 py-1 text-xs"
          @click="filtro = null"
        >
          Só {{ tituloDoFiltro?.toLowerCase() }} · mostrar todos
        </button>
      </div>
      <p
        v-if="!estoque.alertas.length"
        class="cartao mt-3 flex items-center gap-3 p-4 text-sm text-stone-600"
      >
        <IconeSvg
          nome="confirmado"
          class="h-6 w-6 shrink-0 text-campo-500"
        />
        Nenhum alerta hoje. Os insumos estão dentro do esperado para o consumo registrado.
      </p>
      <!-- Ao filtrar, quem fica desliza para o lugar e quem sai esmaece; ao carregar, os
           cartões chegam em cascata, os mais graves primeiro. -->
      <TransitionGroup
        v-else
        tag="ul"
        name="lista"
        class="relative mt-3 space-y-2"
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

    <section
      v-if="reposicoes.length"
      aria-labelledby="titulo-reposicao"
      class="cartao mt-8 overflow-hidden"
    >
      <div class="flex flex-wrap items-center justify-between gap-3 border-b border-stone-100 px-5 py-4">
        <div>
          <h2
            id="titulo-reposicao"
            class="text-base font-semibold text-stone-900"
          >
            Reposição estimada
          </h2>
          <p class="text-sm text-stone-500">
            O que pedir e até quando, com a conta.
          </p>
        </div>
        <!-- No celular, mandar a lista pelo WhatsApp é a ação principal: vem primeiro, na
             largura toda. -->
        <div class="flex flex-wrap gap-2 max-sm:w-full">
          <button
            v-if="podeCopiar"
            type="button"
            class="botao-texto"
            aria-live="polite"
            @click="copiar"
          >
            <IconeSvg
              :nome="copia === 'copiada' ? 'confirmado' : 'copiar'"
              class="h-4 w-4"
            />
            {{ copia ? rotuloDaCopia[copia] : 'Copiar lista' }}
          </button>
          <a
            :href="linkWhatsApp"
            target="_blank"
            rel="noopener"
            class="botao-primario max-sm:order-first max-sm:w-full"
            data-teste="whatsapp"
          >
            <IconeSvg
              nome="enviar"
              class="h-4 w-4"
            />
            Enviar pelo WhatsApp
          </a>
        </div>
      </div>
      <ul class="divide-y divide-stone-100">
        <li
          v-for="item in reposicoes"
          :key="item.insumo.id"
          class="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:gap-6"
          data-teste="reposicao"
        >
          <div class="shrink-0 sm:w-52">
            <RouterLink
              :to="{ name: 'insumo', params: { id: item.insumo.id } }"
              class="text-sm font-medium text-stone-700 hover:text-campo-700 hover:underline"
            >
              {{ item.insumo.nome }}
            </RouterLink>
            <p class="text-2xl font-bold text-stone-900 tabular-nums">
              {{ item.quantidade.toLocaleString('pt-BR') }}
              <span class="text-base font-medium text-stone-500">{{ item.insumo.unidade }}</span>
            </p>
            <p
              v-if="item.custo_estimado !== null"
              class="text-sm text-stone-600 tabular-nums"
            >
              cerca de {{ reais(item.custo_estimado) }}
            </p>
          </div>
          <div class="min-w-0 flex-1">
            <span
              class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset"
              :class="item.pedir_hoje ? 'bg-red-50 text-red-700 ring-red-600/20' : 'bg-stone-50 text-stone-600 ring-stone-300'"
            >
              <IconeSvg
                :nome="item.pedir_hoje ? 'urgente' : 'calendario'"
                class="h-3.5 w-3.5"
              />
              {{ quando(item) }}
            </span>
            <p class="mt-1.5 text-sm leading-relaxed text-stone-600">
              {{ item.justificativa }}
            </p>
          </div>
        </li>
      </ul>
    </section>

    <section
      aria-labelledby="titulo-limitacoes"
      class="mt-8"
    >
      <h2
        id="titulo-limitacoes"
        class="text-base font-semibold text-stone-900"
      >
        Limitações da análise
      </h2>
      <p class="mt-0.5 text-sm text-stone-500">
        O que a conta não sabe, por insumo. Leia antes de decidir uma compra.
      </p>
      <div class="cartao mt-3 divide-y divide-stone-100">
        <details
          v-for="insumo in estoque.insumos"
          :key="insumo.id"
          class="group px-4 py-3"
        >
          <summary class="flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-stone-800 [&::-webkit-details-marker]:hidden">
            <!-- A seta gira ao abrir: mostra que o item abre e em que estado está. -->
            <IconeSvg
              nome="seta"
              class="h-4 w-4 text-stone-400 transition-transform duration-200 ease-movimento group-open:rotate-90"
            />
            {{ insumo.nome }}
            <span class="font-normal text-stone-500">({{ insumo.analise.limitacoes.length }})</span>
          </summary>
          <ul class="mt-2 ml-6 animate-surgir list-disc space-y-1 pl-4 text-sm text-stone-600">
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
