<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import IconeSvg from '@/components/IconeSvg.vue'
import { itensDeMenu } from '@/router'
import { useEstoqueStore } from '@/stores/estoque'
import { useStatusSistemaStore } from '@/stores/statusSistema'

const status = useStatusSistemaStore()
const estoque = useEstoqueStore()
const rota = useRoute()

// Gaveta do celular. No desktop (lg+) o menu é fixo e isto não tem efeito.
const gavetaAberta = ref(false)
watch(
  () => rota.fullPath,
  () => (gavetaAberta.value = false),
)

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
    <!-- Barra superior: só no celular/tablet -->
    <header
      class="sticky top-0 z-30 flex h-14 items-center justify-between bg-campo-700 px-4 text-white lg:hidden"
    >
      <RouterLink
        :to="{ name: 'painel' }"
        class="text-lg font-semibold tracking-tight"
      >
        CampoCerto
      </RouterLink>
      <button
        type="button"
        class="rounded p-2 hover:bg-campo-600"
        :aria-expanded="gavetaAberta"
        aria-controls="menu-lateral"
        aria-label="Abrir menu"
        @click="gavetaAberta = true"
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
      @click="gavetaAberta = false"
    />

    <aside
      id="menu-lateral"
      class="fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-campo-900 text-campo-50 transition-transform duration-200 lg:sticky lg:top-0 lg:h-screen lg:translate-x-0"
      :class="gavetaAberta ? 'translate-x-0' : '-translate-x-full'"
    >
      <div class="flex h-16 items-center justify-between px-5">
        <RouterLink
          :to="{ name: 'painel' }"
          class="text-xl font-semibold tracking-tight text-white"
        >
          CampoCerto
        </RouterLink>
        <button
          type="button"
          class="rounded p-1.5 hover:bg-white/10 lg:hidden"
          aria-label="Fechar menu"
          @click="gavetaAberta = false"
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
          exact-active-class="bg-white/15 text-white"
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

    <div class="flex min-w-0 flex-1 flex-col">
      <main class="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 lg:px-10 lg:py-10">
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
