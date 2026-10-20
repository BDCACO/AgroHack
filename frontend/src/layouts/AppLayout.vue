<script setup lang="ts">
import { nextTick, onMounted, ref, useTemplateRef, watch } from 'vue'
import { useRoute } from 'vue-router'

import IconeSvg from '@/components/IconeSvg.vue'
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

const resumoStatus = {
  verificando: { texto: 'Verificando sistema…', ponto: 'bg-stone-400 animate-pulse' },
  operando: { texto: 'Sistema operando', ponto: 'bg-green-400' },
  problema: { texto: 'Sistema com problema', ponto: 'bg-red-400' },
  'nao-verificado': { texto: 'Sistema não verificado', ponto: 'bg-stone-400' },
} as const

onMounted(() => status.verificar())
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
      class="sticky top-0 z-30 flex h-14 items-center justify-between bg-campo-700 px-4 text-white lg:hidden"
      :inert="gavetaAberta"
    >
      <RouterLink
        :to="{ name: 'painel' }"
        class="text-lg font-semibold tracking-tight"
      >
        CampoCerto
      </RouterLink>
      <button
        ref="botaoAbrir"
        type="button"
        class="rounded p-2 hover:bg-campo-600"
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

    <!-- Fundo escurecido atrás da gaveta -->
    <div
      v-if="gavetaAberta"
      class="fixed inset-0 z-40 bg-black/40 lg:hidden"
      aria-hidden="true"
      @click="fecharGaveta"
    />

    <aside
      id="menu-lateral"
      class="fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-campo-900 text-campo-50 duration-200 lg:sticky lg:top-0 lg:h-screen lg:translate-x-0"
      :class="gavetaAberta ? 'translate-x-0 transition-[translate]' : '-translate-x-full transition-[translate,visibility] max-lg:invisible'"
      @keydown.esc="fecharGaveta"
    >
      <!-- Fechada no celular, `invisible` a tira do Tab e do leitor de tela: sem isso, o
           foco andava pelos links escondidos fora da tela. A visibilidade só entra na
           animação ao fechar (some no fim do deslize); ao abrir, aparece na hora — senão o
           foco não entra nela, que no primeiro instante ainda estaria escondida. -->
      <div class="flex h-16 items-center justify-between px-5">
        <RouterLink
          :to="{ name: 'painel' }"
          class="text-xl font-semibold tracking-tight text-white"
        >
          CampoCerto
        </RouterLink>
        <button
          ref="botaoFechar"
          type="button"
          class="rounded p-1.5 hover:bg-white/10 lg:hidden"
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
        class="flex-1 space-y-1 px-3 py-2"
        aria-label="Principal"
      >
        <RouterLink
          v-for="item in itensDeMenu"
          :key="item.nome"
          :to="{ name: item.nome }"
          class="flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium text-campo-100 hover:bg-white/10 hover:text-white"
          :class="item.nome === (rota.meta.secao ?? rota.name) ? 'bg-white/15 text-white' : ''"
        >
          <IconeSvg
            :nome="item.icone"
            class="h-5 w-5 shrink-0"
          />
          {{ item.rotulo }}
        </RouterLink>
      </nav>

      <RouterLink
        :to="{ name: 'sistema' }"
        class="mx-3 mb-4 flex items-center gap-2 rounded-md px-3 py-2 text-xs text-campo-100 hover:bg-white/10"
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
          class="mb-6 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
          data-teste="aviso-demonstracao"
        >
          <strong>Dados de demonstração.</strong> Parte dos insumos e movimentações foi gerada
          para apresentar o sistema e não vem de uma fazenda real. Para apagar:
          <code>make demo-limpar</code>.
        </p>
        <RouterView />
      </main>
      <footer class="border-t border-stone-200 px-4 py-4 text-center text-xs text-stone-500">
        CampoCerto · AGROHACK 2026/2 · IFRO Campus Ariquemes
      </footer>
    </div>
  </div>
</template>
