<script setup lang="ts">
import { onMounted } from 'vue'

import IndicadorDeStatus from '@/components/IndicadorDeStatus.vue'
import { useStatusSistemaStore } from '@/stores/statusSistema'

const status = useStatusSistemaStore()

onMounted(() => status.verificar())
</script>

<template>
  <section class="space-y-2">
    <h1 class="text-2xl font-semibold text-campo-900">
      CampoCerto
    </h1>
    <p class="max-w-2xl text-stone-600">
      Gestão inteligente de insumos rurais. A base do projeto está no ar; as funcionalidades de
      estoque e análise entram nas próximas etapas.
    </p>
  </section>

  <section class="mt-8 max-w-md">
    <div class="flex items-center justify-between">
      <h2 class="text-sm font-semibold uppercase tracking-wide text-stone-500">
        Situação do sistema
      </h2>
      <button
        type="button"
        class="rounded bg-campo-600 px-3 py-1.5 text-sm text-white hover:bg-campo-700 disabled:opacity-50"
        :disabled="status.verificando"
        @click="status.verificar()"
      >
        {{ status.verificando ? 'Verificando…' : 'Verificar novamente' }}
      </button>
    </div>
    <div class="mt-2 divide-y divide-stone-200 border-y border-stone-200">
      <IndicadorDeStatus
        rotulo="API"
        :estado="status.api"
      />
      <IndicadorDeStatus
        rotulo="Banco de dados"
        :estado="status.banco"
      />
    </div>
  </section>
</template>
