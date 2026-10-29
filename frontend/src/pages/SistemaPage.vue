<script setup lang="ts">
import { onMounted, ref } from 'vue'

import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import GradeDeMesesDeSafra from '@/components/GradeDeMesesDeSafra.vue'
import IconeSvg from '@/components/IconeSvg.vue'
import IndicadorDeStatus from '@/components/IndicadorDeStatus.vue'
import * as api from '@/services/configuracao'
import { mensagemDeErro } from '@/stores/estoque'
import { useSessaoStore } from '@/stores/sessao'
import { useStatusSistemaStore } from '@/stores/statusSistema'

const status = useStatusSistemaStore()
const sessao = useSessaoStore()

const mesesDeSafra = ref<number[]>([])
const salvando = ref(false)
const salvo = ref(false)
const erro = ref<string | null>(null)

onMounted(async () => {
  if (!sessao.podeGerir) return
  try {
    mesesDeSafra.value = (await api.buscarConfiguracao()).meses_de_safra
  } catch (e) {
    erro.value = mensagemDeErro(e)
  }
})

async function salvar() {
  salvando.value = true
  salvo.value = false
  erro.value = null
  try {
    mesesDeSafra.value = (
      await api.salvarConfiguracao({ meses_de_safra: mesesDeSafra.value })
    ).meses_de_safra
    salvo.value = true
  } catch (e) {
    erro.value = mensagemDeErro(e)
  } finally {
    salvando.value = false
  }
}
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

  <div
    v-if="sessao.podeGerir"
    data-teste="calendario-de-safra"
    class="cartao mt-6 max-w-lg animate-surgir p-5"
  >
    <h2 class="text-sm font-semibold text-stone-900">
      Calendário de safra
    </h2>
    <p class="mt-1 text-xs text-stone-500">
      Marque os meses de safra. Com isso, o motor de análise não confunde consumo de
      entressafra com o ritmo da safra, e os alertas de estoque mínimo ficam menos
      urgentes fora de época. Vazio: a análise ignora a época do ano, como sempre.
    </p>
    <GradeDeMesesDeSafra
      v-model="mesesDeSafra"
      class="mt-3"
    />
    <p
      v-if="erro"
      role="alert"
      class="mt-3 text-sm text-red-700"
    >
      {{ erro }}
    </p>
    <div class="mt-4 flex items-center gap-3">
      <button
        type="button"
        data-teste="salvar-calendario"
        class="botao-primario"
        :disabled="salvando"
        @click="salvar"
      >
        {{ salvando ? 'Salvando…' : 'Salvar' }}
      </button>
      <span
        v-if="salvo"
        class="text-sm text-campo-700"
      >Salvo.</span>
    </div>
  </div>
</template>
