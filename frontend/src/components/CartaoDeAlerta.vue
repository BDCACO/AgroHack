<script setup lang="ts">
import type { Alerta, TipoAlerta } from '@/types/api'

import IconeSvg from './IconeSvg.vue'
import SeloDeGravidade from './SeloDeGravidade.vue'

// Uma linha da lista de alertas. Sem `insumo`, está na página do próprio insumo e não
// repete o nome.
defineProps<{ alerta: Alerta; insumo?: { id: number; nome: string } }>()

const rotulo: Record<TipoAlerta, string> = {
  abaixo_do_minimo: 'Abaixo do mínimo',
  risco_de_falta: 'Risco de falta',
  vencido: 'Lote vencido',
  vencimento_proximo: 'Vencimento próximo',
  excesso: 'Excesso de estoque',
  baixa_movimentacao: 'Baixa movimentação',
  consumo_incomum: 'Consumo incomum',
}
</script>

<template>
  <li
    class="group relative flex flex-col gap-1.5 px-5 py-4 transition-colors duration-150 sm:flex-row sm:gap-5"
    :class="insumo ? 'hover:bg-papel/70' : ''"
    data-teste="alerta"
  >
    <div class="shrink-0 pt-0.5 sm:w-20">
      <SeloDeGravidade :gravidade="alerta.gravidade" />
    </div>
    <div class="min-w-0 flex-1">
      <p class="font-medium text-tinta">
        {{ rotulo[alerta.tipo] }}<template v-if="insumo">
          ·
          <!-- O ::after cobre a linha inteira (clicável em qualquer ponto), mas o leitor de
               tela anuncia só o nome como link. -->
          <RouterLink
            :to="{ name: 'insumo', params: { id: insumo.id } }"
            class="after:absolute after:inset-0 after:content-[''] focus-visible:outline-none [&:focus-visible]:after:ring-2 [&:focus-visible]:after:ring-campo-700 [&:focus-visible]:after:ring-inset"
          >
            {{ insumo.nome }}
          </RouterLink>
        </template>
      </p>
      <p class="mt-0.5 text-sm leading-relaxed text-tinta-2">
        {{ alerta.justificativa }}
      </p>
    </div>
    <IconeSvg
      v-if="insumo"
      nome="seta"
      class="hidden size-4 shrink-0 self-center text-tinta-3 opacity-0 transition duration-150 group-hover:translate-x-0.5 group-hover:opacity-100 sm:block"
    />
  </li>
</template>
