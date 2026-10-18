<script setup lang="ts">
import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import IndicadorDeStatus from '@/components/IndicadorDeStatus.vue'
import { useStatusSistemaStore } from '@/stores/statusSistema'

const status = useStatusSistemaStore()
</script>

<template>
  <CabecalhoDePagina
    titulo="Sistema"
    descricao="Situação dos serviços que o CampoCerto usa."
  >
    <template #acoes>
      <button
        type="button"
        class="rounded-md bg-campo-600 px-4 py-2 text-sm font-medium text-white hover:bg-campo-700 disabled:opacity-50"
        :disabled="status.verificando"
        @click="status.verificar()"
      >
        {{ status.verificando ? 'Verificando…' : 'Verificar novamente' }}
      </button>
    </template>
  </CabecalhoDePagina>

  <div class="mt-4 max-w-lg divide-y divide-stone-200 border-b border-stone-200">
    <IndicadorDeStatus
      rotulo="API"
      :estado="status.api"
    />
    <IndicadorDeStatus
      rotulo="Banco de dados"
      :estado="status.banco"
    />
  </div>
  <p
    v-if="status.verificadoEm"
    class="mt-3 text-xs text-stone-500"
  >
    Última verificação: {{ status.verificadoEm.toLocaleTimeString('pt-BR') }}
  </p>
</template>
