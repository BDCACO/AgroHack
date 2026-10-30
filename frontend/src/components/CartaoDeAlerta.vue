<script setup lang="ts">
import type { Alerta, TipoAlerta } from '@/types/api'

import IconeSvg from './IconeSvg.vue'
import SeloDeGravidade from './SeloDeGravidade.vue'

// Sem `insumo`, o cartão está na página do próprio insumo e não repete o nome.
defineProps<{ alerta: Alerta; insumo?: { id: number; nome: string } }>()

const rotulo: Record<TipoAlerta, string> = {
  abaixo_do_minimo: 'Abaixo do mínimo',
  risco_de_falta: 'Risco de falta',
  vencido: 'Lote vencido',
  vencimento_proximo: 'Vencimento próximo',
  excesso: 'Excesso de estoque',
  baixa_movimentacao: 'Baixa movimentação',
  consumo_incomum: 'Consumo incomum',
  carencia: 'Em carência',
}

const faixa = { alta: 'bg-red-500', media: 'bg-amber-400', baixa: 'bg-sky-400' } as const
</script>

<template>
  <li
    class="group relative flex flex-col gap-2 overflow-hidden rounded-xl border border-stone-200/80 bg-superficie p-4 pl-5 shadow-xs transition-[translate,box-shadow,border-color] duration-200 ease-chegada sm:flex-row sm:items-start sm:gap-4"
    :class="insumo ? 'hover:-translate-y-0.5 hover:border-stone-300 hover:shadow-md' : ''"
    data-teste="alerta"
  >
    <!-- A faixa à esquerda repete a gravidade: dá para varrer a lista só por ela. -->
    <span
      class="absolute inset-y-0 left-0 w-1"
      :class="faixa[alerta.gravidade]"
      aria-hidden="true"
    />
    <!-- Largura fixa: alinha o texto dos cartões e não deixa o selo esticar no celular. -->
    <div class="shrink-0 sm:w-24">
      <SeloDeGravidade :gravidade="alerta.gravidade" />
    </div>
    <div class="min-w-0 flex-1">
      <p class="font-semibold text-stone-900">
        {{ rotulo[alerta.tipo] }}<template v-if="insumo">
          ·
          <!-- O after cobre o cartão inteiro: clica-se em qualquer lugar dele, mas o link
               que o leitor de tela anuncia é só o nome. -->
          <RouterLink
            :to="{ name: 'insumo', params: { id: insumo.id } }"
            class="after:absolute after:inset-0 after:content-[''] focus-visible:outline-none group-hover:text-campo-800 [&:focus-visible]:after:rounded-xl [&:focus-visible]:after:ring-2 [&:focus-visible]:after:ring-campo-600"
          >
            {{ insumo.nome }}
          </RouterLink>
        </template>
      </p>
      <p class="mt-0.5 text-sm leading-relaxed text-stone-600">
        {{ alerta.justificativa }}
      </p>
    </div>
    <IconeSvg
      v-if="insumo"
      nome="seta"
      class="hidden h-5 w-5 shrink-0 self-center text-stone-300 transition-[translate,color] duration-200 ease-chegada group-hover:translate-x-1 group-hover:text-campo-600 sm:block"
    />
  </li>
</template>
