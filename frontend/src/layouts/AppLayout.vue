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
    // Numa página que troca sem recarregar, o leitor de tela não percebe a mudança: o
    // foco vai para o conteúdo novo, e o próximo Tab anda por ele, não pelo menu de novo.
    await nextTick()
    conteudo.value?.focus()
  },
)

// O foco entra na gaveta ao abrir e volta ao botão ao fechar: quem usa teclado ou leitor
// de tela não fica perdido atrás do fundo escurecido.
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
  verificando: { texto: 'Verificando sistema…', ponto: 'bg-stone-400 animate-pulse' },
  operando: { texto: 'Sistema operando', ponto: 'bg-green-400' },
  problema: { texto: 'Sistema com problema', ponto: 'bg-red-400' },
  'nao-verificado': { texto: 'Sistema não verificado', ponto: 'bg-stone-400' },
} as const

// O número no item "Painel" do menu: o que não pode esperar fica à vista em qualquer tela.
const urgentes = computed(() => estoque.alertas.filter((a) => a.alerta.gravidade === 'alta').length)

onMounted(() => {
  status.verificar()
  // O contador do menu e o aviso de demonstração valem em qualquer tela. A página monta
  // antes do layout: se ela já pediu os dados, não se pede de novo.
  if (!estoque.carregado && !estoque.carregando) estoque.carregar()
})
</script>

<template>
  <div class="min-h-screen lg:flex">
    <a
      href="#conteudo"
      class="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[60] focus:rounded-md focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-campo-900 focus:shadow-lg"
    >
      Pular para o conteúdo
    </a>

    <!-- Barra superior: só no celular/tablet -->
    <header
      class="sticky top-0 z-30 flex h-14 items-center justify-between bg-campo-900/95 px-4 text-white shadow-sm backdrop-blur lg:hidden"
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
        class="rounded-lg p-2 transition-colors hover:bg-white/10 active:scale-95"
        :aria-expanded="gavetaAberta"
        aria-controls="menu-lateral"
        aria-label="Abrir menu"
        @click="abrirGaveta"
      >
        <IconeSvg
          nome="menu"
          class="h-6 w-6"
        />
      </button>
    </header>

    <!-- Fundo escurecido atrás da gaveta: esmaece junto com o deslize dela. -->
    <Transition
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
      enter-active-class="transition-opacity duration-200 ease-out"
      leave-active-class="transition-opacity duration-150 ease-in"
    >
      <div
        v-if="gavetaAberta"
        class="fixed inset-0 z-40 bg-campo-950/50 backdrop-blur-[2px] lg:hidden"
        aria-hidden="true"
        @click="fecharGaveta"
      />
    </Transition>

    <aside
      id="menu-lateral"
      class="fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-linear-to-b from-campo-900 to-campo-950 text-campo-50 shadow-xl lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 lg:shadow-none"
      :class="gavetaAberta ? 'translate-x-0 transition-[translate] duration-300 ease-chegada' : '-translate-x-full transition-[translate,visibility] duration-200 ease-saida max-lg:invisible'"
      @keydown.esc="fecharGaveta"
    >
      <!-- Fechada no celular, `invisible` a tira do Tab e do leitor de tela: sem isso, o
           foco andava pelos links escondidos fora da tela. A visibilidade só entra na
           animação ao fechar (some no fim do deslize); ao abrir, aparece na hora — senão o
           foco não entra nela, que no primeiro instante ainda estaria escondida. -->
      <div class="flex h-18 items-center justify-between px-5">
        <RouterLink
          :to="{ name: 'painel' }"
          class="text-white"
          aria-label="CampoCerto, ir para o Painel"
        >
          <LogoCampoCerto com-nome />
        </RouterLink>
        <button
          ref="botaoFechar"
          type="button"
          class="rounded-lg p-1.5 transition-colors hover:bg-white/10 active:scale-95 lg:hidden"
          aria-label="Fechar menu"
          @click="fecharGaveta"
        >
          <IconeSvg
            nome="fechar"
            class="h-5 w-5"
          />
        </button>
      </div>

      <nav
        class="relative flex-1 space-y-1 px-3 py-3"
        aria-label="Principal"
      >
        <!-- O destaque da página atual é um só e desliza até o item novo ao navegar: o olho
             vê de onde saiu e aonde chegou. Itens de altura fixa (h-10 + space-y-1), para
             o deslocamento ser a posição vezes 2,75rem. -->
        <span
          class="pointer-events-none absolute inset-x-3 top-3 h-10 rounded-lg bg-white/15 transition-[translate,opacity] duration-300 ease-movimento"
          :class="indiceAtivo < 0 ? 'opacity-0' : ''"
          :style="{ translate: `0 calc(${Math.max(indiceAtivo, 0)} * 2.75rem)` }"
          aria-hidden="true"
        >
          <span class="absolute inset-y-2 left-0 w-1 rounded-r-full bg-campo-300" />
        </span>
        <RouterLink
          v-for="item in itensDeMenu"
          :key="item.nome"
          v-slot="{ href, navigate }"
          :to="{ name: item.nome }"
          custom
        >
          <a
            :href="href"
            class="group relative flex h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors duration-150"
            :class="ativo(item.nome) ? 'text-white' : 'text-campo-100/80 hover:bg-white/5 hover:text-white'"
            :aria-current="ativo(item.nome) ? 'page' : undefined"
            @click="navigate"
          >
            <IconeSvg
              :nome="item.icone"
              class="h-5 w-5 shrink-0 transition-transform duration-150 ease-chegada group-hover:scale-110"
            />
            <span data-teste="rotulo-menu">{{ item.rotulo }}</span>
            <span
              v-if="item.nome === 'painel' && urgentes"
              class="ml-auto rounded-full bg-red-500 px-2 py-0.5 text-xs font-bold text-white"
              data-teste="urgentes-menu"
            >
              {{ urgentes }}<span class="sr-only"> {{ urgentes === 1 ? 'urgente' : 'urgentes' }}</span>
            </span>
          </a>
        </RouterLink>
      </nav>

      <RouterLink
        :to="{ name: 'sistema' }"
        class="mx-3 mb-4 flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-campo-100/80 transition-colors hover:bg-white/5 hover:text-white"
        data-teste="resumo-status"
      >
        <span
          class="h-2 w-2 rounded-full"
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
        class="mx-auto w-full max-w-6xl flex-1 px-4 py-6 focus:outline-none sm:px-6 lg:px-10 lg:py-10"
      >
        <!-- Dado fictício nunca aparece sem aviso: é o que separa demonstração de invenção. -->
        <p
          v-if="estoque.insumos.some((insumo) => insumo.demonstracao)"
          role="note"
          class="mb-6 animate-surgir rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
          data-teste="aviso-demonstracao"
        >
          <strong>Dados de demonstração.</strong> Parte dos insumos e movimentações foi gerada
          para apresentar o sistema e não vem de uma fazenda real. Para apagar:
          <code>make demo-limpar</code>.
        </p>
        <!-- Páginas têm mais de um elemento na raiz: o div dá à transição um só a animar. -->
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
      <footer class="border-t border-stone-200 px-4 py-4 text-center text-xs text-stone-500">
        CampoCerto · AGROHACK 2026/2 · IFRO Campus Ariquemes
      </footer>
    </div>
  </div>
</template>
