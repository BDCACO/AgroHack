<script setup lang="ts">
import type { LinhaLegivel } from '@/auditoriaLegivel'

// Os dados de um registro da Auditoria em palavras. Lista e objeto dentro de objeto (os itens
// de um pedido, o que a demonstração criou) descem um nível, com um fio à esquerda.
defineProps<{ linhas: LinhaLegivel[] }>()
</script>

<template>
  <dl class="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1.5">
    <template
      v-for="(linha, indice) in linhas"
      :key="indice"
    >
      <dt
        class="font-medium text-stone-600"
        :class="linha.filhos ? 'col-span-2' : ''"
      >
        {{ linha.rotulo }}
      </dt>
      <dd
        v-if="linha.filhos"
        class="col-span-2 border-l-2 border-campo-200 pl-3"
      >
        <DadosLegiveis :linhas="linha.filhos" />
      </dd>
      <dd
        v-else
        class="break-words text-stone-900"
      >
        {{ linha.valor }}
      </dd>
    </template>
  </dl>
</template>
