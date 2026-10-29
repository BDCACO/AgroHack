<script setup lang="ts">
import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import IconeSvg from '@/components/IconeSvg.vue'
import IndicadorDeStatus from '@/components/IndicadorDeStatus.vue'
import { useStatusSistemaStore } from '@/stores/statusSistema'

const status = useStatusSistemaStore()
</script>

<template>
  <CabecalhoDePagina
    titulo="Sistema"
  >
    <template #acoes>
      <button
        type="button"
        class="botao-primario"
        :disabled="status.verificando"
        @click="status.verificar()"
      >
        <!-- Gira enquanto verifica: o pedido está andando. -->
        <IconeSvg
          nome="atualizar"
          class="h-4 w-4"
          :class="status.verificando ? 'animate-spin' : ''"
        />
        {{ status.verificando ? 'Verificando…' : 'Verificar novamente' }}
      </button>
    </template>
  </CabecalhoDePagina>

  <div class="cartao max-w-lg animate-surgir divide-y divide-stone-100 px-5">
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
