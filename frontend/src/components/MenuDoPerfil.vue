<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, useTemplateRef, watch } from 'vue'
import { useRoute } from 'vue-router'

import type { Usuario } from '@/types/api'

import IconeSvg from './IconeSvg.vue'

// O perfil na barra do topo: um botão com quem está usando, que abre um menu pequeno no canto
// com o caminho para o perfil (Configurações) e o "Sair". Fecha com Esc, com o clique fora, ao
// escolher e ao trocar de página; as setas andam entre as opções, como num menu do sistema.
const props = defineProps<{ usuario: Usuario }>()
const emit = defineEmits<{ sair: [] }>()
const rota = useRoute()

const rotuloDoPapel = { dono: 'Dono', funcionario: 'Funcionário' } as const
/** "Maria da Silva" vira "MS"; um nome só, a primeira letra. */
const iniciais = (nome: string) => {
  const partes = nome.trim().split(/\s+/)
  return ((partes[0]?.[0] ?? '') + (partes.length > 1 ? (partes.at(-1)?.[0] ?? '') : '')).toUpperCase()
}

const aberto = ref(false)
const raiz = useTemplateRef<HTMLElement>('raiz')
const botao = useTemplateRef<HTMLButtonElement>('botao')
const opcoes = () => [...(raiz.value?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [])]

async function abrir() {
  aberto.value = true
  await nextTick()
  opcoes()[0]?.focus()
}
function fechar(devolverFoco = false) {
  aberto.value = false
  if (devolverFoco) botao.value?.focus()
}
const alternar = () => (aberto.value ? fechar() : abrir())

// Clique fora do menu fecha; o ouvinte só existe enquanto ele está aberto.
function aoClicarFora(evento: PointerEvent) {
  if (!raiz.value?.contains(evento.target as Node)) fechar()
}
watch(aberto, (agora) => {
  if (agora) document.addEventListener('pointerdown', aoClicarFora)
  else document.removeEventListener('pointerdown', aoClicarFora)
})
onBeforeUnmount(() => document.removeEventListener('pointerdown', aoClicarFora))
watch(() => rota.fullPath, () => fechar())

function aoTeclar(evento: KeyboardEvent) {
  if (evento.key === 'Escape') {
    evento.preventDefault()
    fechar(true)
    return
  }
  if (evento.key !== 'ArrowDown' && evento.key !== 'ArrowUp') return
  evento.preventDefault()
  const lista = opcoes()
  const atual = lista.indexOf(document.activeElement as HTMLElement)
  const passo = evento.key === 'ArrowDown' ? 1 : -1
  lista[(atual + passo + lista.length) % lista.length]?.focus()
}

function sair() {
  fechar()
  emit('sair')
}
</script>

<template>
  <div
    ref="raiz"
    class="relative"
    @keydown="aoTeclar"
  >
    <button
      ref="botao"
      type="button"
      class="flex items-center gap-2.5 rounded-lg py-1 pr-2 pl-1 transition-colors hover:bg-stone-100"
      :class="aberto ? 'bg-stone-100' : ''"
      aria-haspopup="menu"
      :aria-expanded="aberto"
      aria-controls="menu-do-perfil"
      data-teste="abrir-perfil"
      @click="alternar"
    >
      <span
        class="grid size-8 place-items-center rounded-full bg-campo-600 text-xs font-semibold text-white"
        aria-hidden="true"
      >{{ iniciais(props.usuario.nome) }}</span>
      <span class="text-left leading-tight">
        <span class="block max-w-40 truncate text-sm font-medium text-stone-900">{{ props.usuario.nome }}</span>
        <span class="block text-xs text-stone-500">{{ rotuloDoPapel[props.usuario.papel] }}</span>
      </span>
      <IconeSvg
        nome="seta"
        class="h-4 w-4 text-stone-400 transition-transform duration-200 ease-chegada"
        :class="aberto ? '-rotate-90' : 'rotate-90'"
      />
    </button>

    <Transition name="menu-perfil">
      <div
        v-if="aberto"
        id="menu-do-perfil"
        role="menu"
        aria-label="Perfil"
        class="cartao absolute top-full right-0 z-50 mt-2 w-64 origin-top-right p-1.5 shadow-lg"
        data-teste="menu-perfil"
      >
        <div class="flex items-center gap-3 px-2.5 pt-2 pb-3">
          <span
            class="grid size-10 shrink-0 place-items-center rounded-full bg-campo-600 text-sm font-semibold text-white"
            aria-hidden="true"
          >{{ iniciais(props.usuario.nome) }}</span>
          <div class="min-w-0 leading-tight">
            <p class="truncate text-sm font-semibold text-stone-900">
              {{ props.usuario.nome }}
            </p>
            <p class="truncate text-xs text-stone-500">
              {{ props.usuario.login }} · {{ rotuloDoPapel[props.usuario.papel] }}
            </p>
          </div>
        </div>
        <div class="border-t border-stone-100 pt-1.5">
          <RouterLink
            :to="{ name: 'configuracoes' }"
            role="menuitem"
            class="flex min-h-10 items-center gap-3 rounded-md px-2.5 text-sm font-medium text-stone-700 transition-colors hover:bg-stone-100 focus:bg-stone-100 focus:outline-none"
            data-teste="ir-perfil"
            @click="fechar()"
          >
            <IconeSvg
              nome="conta"
              class="h-5 w-5 text-stone-500"
            />
            Perfil e configurações
          </RouterLink>
          <button
            type="button"
            role="menuitem"
            class="flex min-h-10 w-full items-center gap-3 rounded-md px-2.5 text-sm font-medium text-red-700 transition-colors hover:bg-red-50 focus:bg-red-50 focus:outline-none"
            data-teste="sair"
            @click="sair"
          >
            <IconeSvg
              nome="sair"
              class="h-5 w-5"
            />
            Sair
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* Abre do canto de onde veio (o botão, em cima à direita), e some mais rápido do que abriu. */
.menu-perfil-enter-active {
  transition:
    opacity 160ms ease-out,
    transform 200ms var(--ease-chegada);
}
.menu-perfil-leave-active {
  transition:
    opacity 120ms var(--ease-saida),
    transform 120ms var(--ease-saida);
}
.menu-perfil-enter-from,
.menu-perfil-leave-to {
  opacity: 0;
  transform: scale(0.96) translateY(-4px);
}
</style>
