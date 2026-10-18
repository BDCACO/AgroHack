<script setup lang="ts">
import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
</script>

<template>
  <CabecalhoDePagina
    titulo="Movimentações"
    descricao="Compras e retiradas registradas, em ordem cronológica."
  />
  <EstadoVazio
    icone="movimentacoes"
    titulo="Nenhuma movimentação registrada"
    texto="Compras e retiradas aparecem aqui depois da primeira importação de dados."
  />
</template>
