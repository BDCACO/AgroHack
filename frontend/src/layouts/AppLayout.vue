<script setup lang="ts">
import { computed, nextTick, onMounted, ref, useTemplateRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import IconeSvg from '@/components/IconeSvg.vue'
import JanelaModal from '@/components/JanelaModal.vue'
import LogoCampoCerto from '@/components/LogoCampoCerto.vue'
import { itensDeMenu } from '@/router'
import { useEstoqueStore } from '@/stores/estoque'
import { useSessaoStore } from '@/stores/sessao'
import { useStatusSistemaStore } from '@/stores/statusSistema'

const status = useStatusSistemaStore()
const estoque = useEstoqueStore()
const sessao = useSessaoStore()
const rota = useRoute()
const router = useRouter()

// O funcionário não vê o que é só do dono (importar planilha): menos telas que dão "peça ao dono".
// Sem login (autenticação desligada), não há usuários nem trilha de quem fez o quê.
const menu = computed(() =>
  itensDeMenu.filter(
    (item) => (!item.soDono || sessao.podeGerir) && (!item.comLogin || sessao.usuario),
  ),
)
// A barra de baixo do celular tem lugar para umas cinco abas: as do dia a dia e o "Mais".
const naBarra = computed(() => menu.value.filter((item) => item.barra))
const noMais = computed(() => menu.value.filter((item) => !item.barra))
const maisAberto = ref(false)
const rotuloDoPapel = { dono: 'Dono', funcionario: 'Funcionário' } as const

async function sair() {
  await sessao.sair()
  await router.replace({ name: 'entrar' })
}

const conteudo = useTemplateRef<HTMLElement>('conteudo')

// Numa página que troca sem recarregar, o leitor de tela não percebe a mudança: o foco vai
// para o conteúdo novo, e o próximo Tab anda por ele, não pelo menu de novo.
watch(
  () => rota.fullPath,
  async () => {
    await nextTick()
    conteudo.value?.focus({ preventScroll: true })
  },
)

const ativo = (nome: string) => nome === (rota.meta.secao ?? rota.name)
const indiceAtivo = computed(() => menu.value.findIndex((item) => ativo(item.nome)))
// Na barra de baixo, tela que não está nela acende o "Mais", a última aba.
const indiceNaBarra = computed(() => {
  const indice = naBarra.value.findIndex((item) => ativo(item.nome))
  return indice >= 0 ? indice : naBarra.value.length
})
// Fecha o "Mais" ao navegar por ele.
watch(() => rota.fullPath, () => (maisAberto.value = false))

// Tocar de novo na aba da tela em que já se está sobe para o topo, como nos apps.
function tocarNaAba(nome: string, navegar: (evento: MouseEvent) => void, evento: MouseEvent) {
  if (rota.name !== nome) return navegar(evento)
  evento.preventDefault()
  const reduzir = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  window.scrollTo({ top: 0, behavior: reduzir ? 'auto' : 'smooth' })
}

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
  // O contador do menu vale em qualquer tela. A página monta
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

    <!-- Barra superior do celular e do tablet: só a marca. Rola junto com a página; quem
         fica sempre à mão é a barra de baixo. No app instalado, desce abaixo do relógio. -->
    <header
      class="flex h-[calc(3.5rem+env(safe-area-inset-top))] items-center bg-campo-900 px-4 pt-[env(safe-area-inset-top)] text-white lg:hidden"
    >
      <RouterLink
        :to="{ name: 'painel' }"
        aria-label="CampoCerto, ir para o Painel"
      >
        <LogoCampoCerto com-nome />
      </RouterLink>
      <button
        v-if="sessao.usuario"
        type="button"
        class="ml-auto min-h-11 rounded-lg px-3 text-sm font-medium text-campo-100 active:bg-white/10"
        :aria-label="`Sair (${sessao.usuario.nome})`"
        @click="sair"
      >
        Sair
      </button>
    </header>

    <!-- Menu lateral: só no desktop. -->
    <aside class="inset-y-0 left-0 z-50 hidden w-64 flex-col bg-linear-to-b from-campo-900 to-campo-950 text-campo-50 lg:sticky lg:top-0 lg:flex lg:h-screen">
      <div class="flex h-18 items-center justify-between px-5">
        <RouterLink
          :to="{ name: 'painel' }"
          class="text-white"
          aria-label="CampoCerto, ir para o Painel"
        >
          <LogoCampoCerto com-nome />
        </RouterLink>
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
          v-for="item in menu"
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
              {{ urgentes }}<span class="sr-only">{{ urgentes === 1 ? ' urgente' : ' urgentes' }}</span>
            </span>
          </a>
        </RouterLink>
      </nav>

      <!-- Quem está usando. Sem login (API de desenvolvimento com a autenticação desligada),
           o caminho para entrar. -->
      <div
        v-if="sessao.usuario"
        class="mx-3 mb-2 flex items-center gap-2 px-3 py-1"
        data-teste="sessao"
      >
        <RouterLink
          :to="{ name: 'conta' }"
          class="-mx-2 min-w-0 flex-1 rounded-md px-2 py-1 transition-colors hover:bg-white/10"
          :class="rota.name === 'conta' ? 'bg-white/15' : ''"
          :aria-current="rota.name === 'conta' ? 'page' : undefined"
          title="Minha conta: senha e aparelhos"
        >
          <p class="truncate text-sm font-medium text-white">
            {{ sessao.usuario.nome }}
          </p>
          <p class="text-xs text-campo-100/70">
            {{ rotuloDoPapel[sessao.usuario.papel] }}
          </p>
        </RouterLink>
        <button
          type="button"
          class="rounded-md px-2 py-1 text-xs font-semibold text-campo-100 transition-colors hover:bg-white/10 hover:text-white"
          @click="sair"
        >
          Sair
        </button>
      </div>
      <RouterLink
        v-else
        :to="{ name: 'entrar' }"
        class="mx-3 mb-2 px-3 py-1 text-xs font-medium text-campo-100/70 hover:text-white"
      >
        Entrar com login
      </RouterLink>
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

    <!-- No celular, a barra de baixo ocupa o fim da tela: o conteúdo termina antes dela. -->
    <div class="flex min-w-0 flex-1 flex-col max-lg:pb-[calc(4rem+env(safe-area-inset-bottom))]">
      <main
        id="conteudo"
        ref="conteudo"
        tabindex="-1"
        class="mx-auto w-full max-w-6xl flex-1 px-4 py-6 focus:outline-none sm:px-6 lg:px-10 lg:py-10"
      >
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

    <!-- Barra de baixo, no celular e no tablet: as telas ao alcance do polegar, sem menu
         escondido. Mesmas telas e mesma ordem do menu lateral. -->
    <nav
      class="barra-inferior fixed inset-x-0 bottom-0 z-40 bg-campo-900 pb-[env(safe-area-inset-bottom)] text-campo-100/75 shadow-[0_-1px_0_rgb(0_0_0/0.15)] lg:hidden"
      aria-label="Principal"
    >
      <div
        class="relative mx-auto grid max-w-xl"
        :style="{ gridTemplateColumns: `repeat(${naBarra.length + 1}, minmax(0, 1fr))` }"
      >
        <!-- Como no menu lateral: um destaque só, que desliza até a aba nova. -->
        <span
          class="pointer-events-none absolute top-2 left-0 flex justify-center transition-[translate,opacity] duration-300 ease-movimento"
          :class="indiceAtivo < 0 && rota.name !== 'conta' ? 'opacity-0' : ''"
          :style="{ width: `${100 / (naBarra.length + 1)}%`, translate: `calc(${indiceNaBarra} * 100%) 0` }"
          aria-hidden="true"
        >
          <span class="h-8 w-14 rounded-full bg-white/15" />
        </span>
        <RouterLink
          v-for="item in naBarra"
          :key="item.nome"
          v-slot="{ href, navigate }"
          :to="{ name: item.nome }"
          custom
        >
          <a
            :href="href"
            class="group relative flex h-16 flex-col items-center justify-start gap-1 pt-2 text-[11px] leading-none font-medium transition-colors duration-150 [-webkit-tap-highlight-color:transparent]"
            :class="ativo(item.nome) ? 'text-white' : 'active:text-white'"
            :aria-current="ativo(item.nome) ? 'page' : undefined"
            data-teste="aba"
            @click="tocarNaAba(item.nome, navigate, $event)"
          >
            <span class="relative flex h-8 w-14 items-center justify-center">
              <IconeSvg
                :nome="item.icone"
                class="h-6 w-6 transition-transform duration-150 ease-chegada group-active:scale-90"
              />
              <span
                v-if="item.nome === 'painel' && urgentes"
                class="absolute top-0 right-2.5 min-w-4 rounded-full bg-red-500 px-1 text-center text-[10px] leading-4 font-bold text-white ring-2 ring-campo-900"
                data-teste="urgentes-aba"
              >
                {{ urgentes }}<span class="sr-only">{{ urgentes === 1 ? ' urgente' : ' urgentes' }}</span>
              </span>
              <span
                v-if="item.nome === 'sistema' && status.situacao === 'problema'"
                class="absolute top-0.5 right-3.5 size-2.5 rounded-full bg-red-400 ring-2 ring-campo-900"
              >
                <span class="sr-only">, com problema</span>
              </span>
            </span>
            <span>{{ item.rotuloCurto }}</span>
          </a>
        </RouterLink>
        <button
          type="button"
          class="group relative flex h-16 flex-col items-center justify-start gap-1 pt-2 text-[11px] leading-none font-medium transition-colors duration-150 [-webkit-tap-highlight-color:transparent]"
          :class="indiceNaBarra === naBarra.length && (indiceAtivo >= 0 || rota.name === 'conta') ? 'text-white' : 'active:text-white'"
          aria-haspopup="dialog"
          data-teste="aba-mais"
          @click="maisAberto = true"
        >
          <span class="relative flex h-8 w-14 items-center justify-center">
            <IconeSvg
              nome="mais"
              class="h-6 w-6 transition-transform duration-150 ease-chegada group-active:scale-90"
            />
            <span
              v-if="noMais.some((item) => item.nome === 'sistema') && status.situacao === 'problema'"
              class="absolute top-0.5 right-3.5 size-2.5 rounded-full bg-red-400 ring-2 ring-campo-900"
            >
              <span class="sr-only">, sistema com problema</span>
            </span>
          </span>
          <span>Mais</span>
        </button>
      </div>
    </nav>

    <!-- O resto das telas, no celular: sobe do pé da tela, perto do dedo. -->
    <JanelaModal
      v-if="maisAberto"
      titulo="Mais"
      @fechar="maisAberto = false"
    >
      <ul
        class="-mx-2 grid gap-1"
        data-teste="menu-mais"
      >
        <li
          v-for="item in noMais"
          :key="item.nome"
        >
          <RouterLink
            :to="{ name: item.nome }"
            class="flex min-h-12 items-center gap-3 rounded-lg px-3 text-sm font-medium text-stone-700 active:bg-stone-100"
            :class="ativo(item.nome) ? 'bg-campo-50 text-campo-800' : ''"
          >
            <IconeSvg
              :nome="item.icone"
              class="h-5 w-5 shrink-0 text-campo-700"
            />
            {{ item.rotulo }}
          </RouterLink>
        </li>
        <li v-if="sessao.usuario">
          <RouterLink
            :to="{ name: 'conta' }"
            class="flex min-h-12 items-center gap-3 rounded-lg px-3 text-sm font-medium text-stone-700 active:bg-stone-100"
            :class="rota.name === 'conta' ? 'bg-campo-50 text-campo-800' : ''"
          >
            <IconeSvg
              nome="conta"
              class="h-5 w-5 shrink-0 text-campo-700"
            />
            Minha conta
            <span class="ml-auto truncate text-xs font-normal text-stone-500">{{ sessao.usuario.nome }}</span>
          </RouterLink>
        </li>
      </ul>
    </JanelaModal>
  </div>
</template>
