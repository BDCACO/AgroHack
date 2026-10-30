<script setup lang="ts">
import { computed, nextTick, onMounted, ref, useTemplateRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import IconeSvg from '@/components/IconeSvg.vue'
import JanelaModal from '@/components/JanelaModal.vue'
import LogoCampoCerto from '@/components/LogoCampoCerto.vue'
import MenuDoPerfil from '@/components/MenuDoPerfil.vue'
import { itensDeMenu } from '@/router'
import { useEstoqueStore } from '@/stores/estoque'
import { useSessaoStore } from '@/stores/sessao'
import { useStatusSistemaStore } from '@/stores/statusSistema'
import { tituloDaPagina } from '@/tituloDaPagina'

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
const REPOSITORIO = 'https://github.com/BDCACO/AgroHack'

// O menu lateral recolhido fica só com os ícones: mais lugar para tabelas e gráficos. A
// escolha é deste navegador; sem armazenamento (aba anônima, site bloqueado), começa aberto.
const CHAVE_DO_MENU = 'campocerto.menu-recolhido'
function lerRecolhido() {
  try {
    return localStorage.getItem(CHAVE_DO_MENU) === '1'
  } catch {
    return false
  }
}
const recolhido = ref(lerRecolhido())
function alternarMenu() {
  recolhido.value = !recolhido.value
  try {
    localStorage.setItem(CHAVE_DO_MENU, recolhido.value ? '1' : '0')
  } catch {
    // Sem armazenamento, vale só até recarregar.
  }
}

// Onde se está, na barra do topo: a seção do menu e, numa página dentro dela, o nome da página.
// O título vem da página (o nome do insumo, e não "Insumo"); enquanto ela carrega, o da rota.
const tituloAtual = computed(() =>
  tituloDaPagina.value?.caminho === rota.path ? tituloDaPagina.value.titulo : rota.meta.titulo,
)
const secaoAtual = computed(() => menu.value.find((item) => ativo(item.nome)))
const paginaDentro = computed(() =>
  secaoAtual.value && rota.name !== secaoAtual.value.nome ? tituloAtual.value : undefined,
)

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
      class="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[60] focus:rounded-md focus:bg-superficie focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-campo-900 focus:shadow-lg"
    >
      Pular para o conteúdo
    </a>

    <!-- Barra superior do celular e do tablet: a marca e o título da página, que dentro dela
         não aparece. Rola junto com a página; quem fica sempre à mão é a barra de baixo. No
         app instalado, desce abaixo do relógio. -->
    <header
      class="flex h-[calc(3.5rem+env(safe-area-inset-top))] cromo items-center gap-3 bg-mata-900 px-4 pt-[env(safe-area-inset-top)] text-white lg:hidden"
    >
      <RouterLink
        :to="{ name: 'painel' }"
        class="shrink-0"
        aria-label="CampoCerto, ir para o Painel"
      >
        <LogoCampoCerto />
      </RouterLink>
      <p
        class="min-w-0 truncate text-lg font-semibold"
        aria-hidden="true"
        data-teste="titulo-celular"
      >
        {{ tituloAtual }}
      </p>
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

    <!-- Menu lateral: só no desktop. Recolhido, fica só com os ícones; o nome de cada tela
         continua para o leitor de tela e aparece ao parar o mouse em cima. -->
    <aside
      id="menu-lateral"
      class="inset-y-0 left-0 z-50 hidden shrink-0 flex-col overflow-hidden cromo bg-linear-to-b from-mata-900 to-mata-950 whitespace-nowrap text-campo-50 transition-[width] duration-300 ease-movimento lg:sticky lg:top-0 lg:flex lg:h-screen"
      :class="recolhido ? 'w-18' : 'w-64'"
      :data-recolhido="recolhido || undefined"
    >
      <div class="flex h-16 items-center px-5">
        <RouterLink
          :to="{ name: 'painel' }"
          class="text-white"
          aria-label="CampoCerto, ir para o Painel"
        >
          <LogoCampoCerto :com-nome="!recolhido" />
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
            class="group relative flex h-10 items-center gap-3 rounded-lg px-3.5 text-sm font-medium transition-colors duration-150"
            :class="ativo(item.nome) ? 'text-white' : 'text-campo-100/80 hover:bg-white/5 hover:text-white'"
            :aria-current="ativo(item.nome) ? 'page' : undefined"
            :title="recolhido ? item.rotulo : undefined"
            @click="navigate"
          >
            <IconeSvg
              :nome="item.icone"
              class="h-5 w-5 shrink-0 transition-transform duration-150 ease-chegada group-hover:scale-110"
            />
            <span
              :class="recolhido ? 'sr-only' : ''"
              data-teste="rotulo-menu"
            >{{ item.rotulo }}</span>
            <!-- Recolhido, o número de urgentes vira um selo no canto do ícone. -->
            <span
              v-if="item.nome === 'painel' && urgentes"
              class="rounded-full bg-red-500 text-xs font-bold text-white"
              :class="recolhido
                ? 'absolute top-0.5 right-1 min-w-4 px-1 text-center text-[10px] leading-4 ring-2 ring-mata-900'
                : 'ml-auto px-2 py-0.5'"
              data-teste="urgentes-menu"
            >
              {{ urgentes }}<span class="sr-only">{{ urgentes === 1 ? ' urgente' : ' urgentes' }}</span>
            </span>
            <!-- A API ou o banco fora do ar: o ponto vermelho em Configurações, onde está o detalhe. -->
            <span
              v-if="item.nome === 'configuracoes' && status.situacao === 'problema'"
              class="size-2.5 rounded-full bg-red-400 ring-2 ring-mata-900"
              :class="recolhido ? 'absolute top-1.5 right-2' : 'ml-auto'"
              data-teste="problema-menu"
            >
              <span class="sr-only">, sistema com problema</span>
            </span>
          </a>
        </RouterLink>
      </nav>
    </aside>

    <!-- No celular, a barra de baixo ocupa o fim da tela: o conteúdo termina antes dela. -->
    <div class="flex min-w-0 flex-1 flex-col max-lg:pb-[calc(4rem+env(safe-area-inset-bottom))]">
      <!-- Barra do topo, no desktop: o botão que recolhe o menu, onde se está, o status do
           sistema e quem está usando. Fica presa no alto ao rolar. -->
      <header
        class="sticky top-0 z-30 hidden h-16 items-center gap-3 border-b border-stone-200/80 bg-superficie/85 px-4 backdrop-blur lg:flex"
        data-teste="barra-do-topo"
      >
        <button
          type="button"
          class="grid size-10 place-items-center rounded-lg text-stone-600 transition-colors hover:bg-stone-100 hover:text-stone-900"
          :aria-label="recolhido ? 'Abrir o menu' : 'Recolher o menu'"
          :title="recolhido ? 'Abrir o menu' : 'Recolher o menu'"
          :aria-expanded="!recolhido"
          aria-controls="menu-lateral"
          data-teste="recolher-menu"
          @click="alternarMenu"
        >
          <IconeSvg
            nome="recolher"
            class="h-5 w-5 transition-transform duration-300 ease-movimento"
            :class="recolhido ? 'rotate-180' : ''"
          />
        </button>
        <nav
          v-if="secaoAtual"
          aria-label="Você está em"
          class="min-w-0"
        >
          <ol class="flex items-center gap-1.5 text-lg">
            <li class="truncate">
              <RouterLink
                v-if="paginaDentro"
                :to="{ name: secaoAtual.nome }"
                class="text-stone-500 hover:text-campo-700 hover:underline"
              >
                {{ secaoAtual.rotulo }}
              </RouterLink>
              <span
                v-else
                class="font-semibold text-stone-900"
                aria-current="page"
              >{{ secaoAtual.rotulo }}</span>
            </li>
            <li
              v-if="paginaDentro"
              class="flex min-w-0 items-center gap-1.5 font-semibold text-stone-900"
              aria-current="page"
            >
              <IconeSvg
                nome="seta"
                class="h-5 w-5 shrink-0 text-stone-400"
              />
              <span class="truncate">{{ paginaDentro }}</span>
            </li>
          </ol>
        </nav>
        <p
          v-else-if="tituloAtual"
          class="truncate text-lg font-semibold text-stone-900"
          aria-hidden="true"
        >
          {{ tituloAtual }}
        </p>

        <div class="ml-auto flex items-center gap-2">
          <!-- O código do projeto, aberto: em outra aba, para não perder a tela em que se está. -->
          <a
            :href="REPOSITORIO"
            target="_blank"
            rel="noopener noreferrer"
            class="flex items-center gap-2 rounded-full border border-stone-200 px-3 py-1.5 text-xs font-medium text-stone-600 transition-colors hover:bg-stone-50 hover:text-stone-900"
            data-teste="link-github"
          >
            <IconeSvg
              nome="github"
              class="h-4 w-4"
            />
            GitHub<span class="sr-only"> (abre em outra aba)</span>
          </a>

          <!-- Quem está usando: o clique abre o menu com o perfil (Configurações) e o "Sair". Sem
               login (API de desenvolvimento com a autenticação desligada), o caminho para entrar. -->
          <div
            v-if="sessao.usuario"
            class="border-l border-stone-200 pl-2"
            data-teste="sessao"
          >
            <MenuDoPerfil
              :usuario="sessao.usuario"
              @sair="sair"
            />
          </div>
          <RouterLink
            v-else
            :to="{ name: 'entrar' }"
            class="botao-secundario py-1.5 text-sm"
          >
            Entrar com login
          </RouterLink>
        </div>
      </header>

      <main
        id="conteudo"
        ref="conteudo"
        tabindex="-1"
        class="mx-auto w-full max-w-6xl flex-1 px-4 py-6 focus:outline-none sm:px-6 lg:px-10 lg:py-8"
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
      class="barra-inferior cromo fixed inset-x-0 bottom-0 z-40 bg-mata-900 pb-[env(safe-area-inset-bottom)] text-campo-100/75 shadow-[0_-1px_0_rgb(0_0_0/0.15)] lg:hidden"
      aria-label="Principal"
    >
      <div
        class="relative mx-auto grid max-w-xl"
        :style="{ gridTemplateColumns: `repeat(${naBarra.length + 1}, minmax(0, 1fr))` }"
      >
        <!-- Como no menu lateral: um destaque só, que desliza até a aba nova. -->
        <span
          class="pointer-events-none absolute top-2 left-0 flex justify-center transition-[translate,opacity] duration-300 ease-movimento"
          :class="indiceAtivo < 0 ? 'opacity-0' : ''"
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
                class="absolute top-0 right-2.5 min-w-4 rounded-full bg-red-500 px-1 text-center text-[10px] leading-4 font-bold text-white ring-2 ring-mata-900"
                data-teste="urgentes-aba"
              >
                {{ urgentes }}<span class="sr-only">{{ urgentes === 1 ? ' urgente' : ' urgentes' }}</span>
              </span>
              <span
                v-if="item.nome === 'configuracoes' && status.situacao === 'problema'"
                class="absolute top-0.5 right-3.5 size-2.5 rounded-full bg-red-400 ring-2 ring-mata-900"
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
          :class="indiceNaBarra === naBarra.length && indiceAtivo >= 0 ? 'text-white' : 'active:text-white'"
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
              v-if="noMais.some((item) => item.nome === 'configuracoes') && status.situacao === 'problema'"
              class="absolute top-0.5 right-3.5 size-2.5 rounded-full bg-red-400 ring-2 ring-mata-900"
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
      </ul>
    </JanelaModal>
  </div>
</template>
