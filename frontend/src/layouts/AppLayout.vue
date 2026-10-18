<script setup lang="ts">
import { ref } from 'vue'

// A navegação cresce junto com as telas; hoje só existe a inicial.
const itens = [{ rotulo: 'Início', para: { name: 'inicio' } }]

const menuAberto = ref(false)
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <header class="bg-campo-700 text-white">
      <div class="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <RouterLink
          :to="{ name: 'inicio' }"
          class="text-lg font-semibold tracking-tight"
        >
          CampoCerto
        </RouterLink>

        <button
          type="button"
          class="rounded p-2 hover:bg-campo-600 md:hidden"
          :aria-expanded="menuAberto"
          aria-controls="menu-principal"
          aria-label="Abrir menu"
          @click="menuAberto = !menuAberto"
        >
          <svg
            class="h-5 w-5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            aria-hidden="true"
          >
            <path d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <nav
          id="menu-principal"
          class="hidden gap-1 md:flex"
        >
          <RouterLink
            v-for="item in itens"
            :key="item.rotulo"
            :to="item.para"
            class="rounded px-3 py-1.5 text-sm hover:bg-campo-600"
            active-class="bg-campo-600"
          >
            {{ item.rotulo }}
          </RouterLink>
        </nav>
      </div>

      <nav
        v-if="menuAberto"
        class="border-t border-campo-600 px-4 py-2 md:hidden"
      >
        <RouterLink
          v-for="item in itens"
          :key="item.rotulo"
          :to="item.para"
          class="block rounded px-3 py-2 text-sm hover:bg-campo-600"
          @click="menuAberto = false"
        >
          {{ item.rotulo }}
        </RouterLink>
      </nav>
    </header>

    <main class="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
      <RouterView />
    </main>

    <footer class="border-t border-stone-200 py-4 text-center text-xs text-stone-500">
      CampoCerto · AGROHACK 2026/2 · IFRO Campus Ariquemes
    </footer>
  </div>
</template>
