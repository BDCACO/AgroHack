<script setup lang="ts">
import { computed, nextTick, onMounted, ref, useTemplateRef, watch } from 'vue'
import { useRoute } from 'vue-router'

import IconeSvg from '@/components/IconeSvg.vue'
import LogoCampoCerto from '@/components/LogoCampoCerto.vue'
import { itensDeMenu } from '@/router'
import { useEstoqueStore } from '@/stores/estoque'
import { useStatusSistemaStore } from '@/stores/statusSistema'

const status = useStatusSistemaStore()
const estoque = useEstoqueStore()
const rota = useRoute()

const conteudo = useTemplateRef<HTMLElement>('conteudo')
const botaoAbrir = useTemplateRef<HTMLButtonElement>('botaoAbrir')
const botaoFechar = useTemplateRef<HTMLButtonElement>('botaoFechar')

// Gaveta do celular. No desktop (lg+) o menu é fixo e isto não tem efeito.
const gavetaAberta = ref(false)
watch(
  () => rota.fullPath,
  async () => {
    gavetaAberta.value = false
    // Página que troca sem recarregar não é percebida pelo leitor de tela: o foco vai para
    // o conteúdo novo, e o Tab seguinte anda por ele, não pelo menu de novo.
    await nextTick()
    conteudo.value?.focus()
  },
)

// O foco entra na gaveta ao abrir e volta ao botão ao fechar.
function abrirGaveta() {
  gavetaAberta.value = true
  nextTick(() => botaoFechar.value?.focus())
}
async function fecharGaveta() {
  gavetaAberta.value = false
  // Depois de a barra deixar de ser inerte: elemento inerte não recebe foco.
  await nextTick()
  botaoAbrir.value?.focus()
}

const ativo = (nome: string) => nome === (rota.meta.secao ?? rota.name)
const indiceAtivo = computed(() => itensDeMenu.findIndex((item) => ativo(item.nome)))

const resumoStatus = {
  verificando: { texto: 'Verificando sistema…', ponto: 'bg-linha-forte animate-brilho' },
  operando: { texto: 'Sistema operando', ponto: 'bg-campo-500' },
  problema: { texto: 'Sistema com problema', ponto: 'bg-urgente' },
  'nao-verificado': { texto: 'Sistema não verificado', ponto: 'bg-linha-forte' },
} as const

// Quantos alertas urgentes há, ao lado de "Painel": vale em qualquer tela.
const urgentes = computed(() => estoque.alertas.filter((a) => a.alerta.gravidade === 'alta').length)

onMounted(() => {
  status.verificar()
  // A página monta antes do layout: se ela já pediu os dados, não se pede de novo.
  if (!estoque.carregado && !estoque.carregando) estoque.carregar()
})
</script>

<template>
  <div class="min-h-screen lg:flex">
    <a
      href="#conteudo"
      class="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[60] focus:rounded-md focus:border focus:border-linha focus:bg-folha focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-tinta"
    >
      Pular para o conteúdo
    </a>

    <!-- Barra superior: só no celular/tablet -->
    <header
      class="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-linha bg-papel/90 px-4 backdrop-blur-sm lg:hidden"
      :inert="gavetaAberta"
    >
      <RouterLink
        :to="{ name: 'painel' }"
        aria-label="CampoCerto, ir para o Painel"
      >
        <LogoCampoCerto com-nome />
      </RouterLink>
      <button
        ref="botaoAbrir"
        type="button"
        class="-mr-2 rounded-md p-2 text-tinta-2 transition-[color,background-color,transform] duration-150 hover:bg-tinta/5 hover:text-tinta active:scale-95"
        :aria-expanded="gavetaAberta"
        aria-controls="menu-lateral"
        aria-label="Abrir menu"
        @click="abrirGaveta"
      >
        <IconeSvg
          nome="menu"
          class="size-6"
        />
      </button>
    </header>

    <!-- Fundo atrás da gaveta: aparece em 200 ms, some em 150. -->
    <Transition
      enter-active-class="transition-opacity duration-200 ease-chegar"
      leave-active-class="transition-opacity duration-150 ease-sair"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div
        v-if="gavetaAberta"
        class="fixed inset-0 z-40 bg-tinta/30 lg:hidden"
        aria-hidden="true"
        @click="fecharGaveta"
      />
    </Transition>

    <!-- Fechada no celular, `invisible` a tira do Tab e do leitor de tela. A visibilidade
         só entra na transição ao fechar (some no fim do deslize); ao abrir, aparece na
         hora, senão o foco não entraria nela. Abre em 300 ms, fecha em 200. -->
    <aside
      id="menu-lateral"
      class="fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-linha bg-papel lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 lg:shadow-none"
      :class="
        gavetaAberta
          ? 'translate-x-0 shadow-2xl shadow-tinta/15 transition-[translate] duration-300 ease-chegar'
          : '-translate-x-full transition-[translate,visibility] duration-200 ease-sair max-lg:invisible'
      "
      @keydown.esc="fecharGaveta"
    >
      <div class="flex h-16 items-center justify-between px-5">
        <RouterLink
          :to="{ name: 'painel' }"
          aria-label="CampoCerto, ir para o Painel"
        >
          <LogoCampoCerto com-nome />
        </RouterLink>
        <button
          ref="botaoFechar"
          type="button"
          class="-mr-1.5 rounded-md p-1.5 text-tinta-2 transition-[color,background-color,transform] duration-150 hover:bg-tinta/5 hover:text-tinta active:scale-95 lg:hidden"
          aria-label="Fechar menu"
          @click="fecharGaveta"
        >
          <IconeSvg
            nome="fechar"
            class="size-5"
          />
        </button>
      </div>

      <nav
        class="flex-1 px-3 py-2"
        aria-label="Principal"
      >
        <div class="relative flex flex-col gap-0.5">
          <!-- Um indicador só, atrás dos itens, que desliza até o ativo ao navegar. Os
               itens têm altura fixa (2,25rem + 0,125rem de espaço), daí a conta. -->
          <span
            class="absolute inset-x-0 top-0 h-9 rounded-md border border-linha bg-folha transition-[translate,opacity] duration-300 ease-mover"
            :class="indiceAtivo < 0 ? 'opacity-0' : ''"
            :style="{ translate: `0 calc(${Math.max(indiceAtivo, 0)} * 2.375rem)` }"
            aria-hidden="true"
          />
          <RouterLink
            v-for="item in itensDeMenu"
            :key="item.nome"
            v-slot="{ href, navigate }"
            :to="{ name: item.nome }"
            custom
          >
            <a
              :href="href"
              class="relative flex h-9 items-center gap-3 rounded-md px-3 text-sm transition-colors duration-150"
              :class="ativo(item.nome) ? 'font-medium text-tinta' : 'text-tinta-2 hover:text-tinta'"
              :aria-current="ativo(item.nome) ? 'page' : undefined"
              @click="navigate"
            >
              <IconeSvg
                :nome="item.icone"
                class="size-[18px] shrink-0 transition-colors duration-150"
                :class="ativo(item.nome) ? 'text-campo-700' : 'text-tinta-3'"
              />
              <span data-teste="rotulo-menu">{{ item.rotulo }}</span>
              <span
                v-if="item.nome === 'painel' && urgentes"
                class="ml-auto rounded bg-urgente-claro px-1.5 text-xs font-semibold text-urgente tabular-nums"
                data-teste="urgentes-menu"
              >
                {{ urgentes }}<span class="sr-only"> {{ urgentes === 1 ? 'urgente' : 'urgentes' }}</span>
              </span>
            </a>
          </RouterLink>
        </div>
      </nav>

      <RouterLink
        :to="{ name: 'sistema' }"
        class="mx-3 mb-4 flex items-center gap-2 rounded-md px-3 py-2 text-xs text-tinta-3 transition-colors duration-150 hover:bg-tinta/5 hover:text-tinta-2"
        data-teste="resumo-status"
      >
        <span
          class="size-1.5 rounded-full"
          :class="resumoStatus[status.situacao].ponto"
          aria-hidden="true"
        />
        {{ resumoStatus[status.situacao].texto }}
      </RouterLink>
    </aside>

    <!-- Com a gaveta aberta, o resto da tela fica inerte: o Tab não escapa para trás dela. -->
    <div
      class="flex min-w-0 flex-1 flex-col"
      :inert="gavetaAberta"
    >
      <main
        id="conteudo"
        ref="conteudo"
        tabindex="-1"
        class="mx-auto w-full max-w-[72rem] flex-1 px-5 py-8 focus:outline-none sm:px-8 lg:px-12 lg:py-12"
      >
        <!-- Dado fictício nunca aparece sem aviso. -->
        <p
          v-if="estoque.insumos.some((insumo) => insumo.demonstracao)"
          role="note"
          class="mb-8 border-l-2 border-atencao-forte py-0.5 pl-3 text-sm leading-relaxed text-tinta-2"
          data-teste="aviso-demonstracao"
        >
          <span class="font-medium text-tinta">Dados de demonstração.</span> Fazenda fictícia,
          gerada para apresentar o sistema. Para apagar: <code class="text-[0.8125rem]">make demo-limpar</code>.
        </p>
        <!-- O div dá à transição um elemento só: as páginas têm mais de um na raiz. -->
        <RouterView v-slot="{ Component, route: atual }">
          <Transition
            name="pagina"
            mode="out-in"
          >
            <div :key="atual.path">
              <component :is="Component" />
            </div>
          </Transition>
        </RouterView>
      </main>
      <footer class="mx-auto w-full max-w-[72rem] border-t border-linha px-5 py-5 text-xs text-tinta-3 sm:px-8 lg:px-12">
        CampoCerto · AGROHACK 2026/2 · IFRO Campus Ariquemes
      </footer>
    </div>
  </div>
</template>
