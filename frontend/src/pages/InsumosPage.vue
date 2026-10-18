<script setup lang="ts">
import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
</script>

<template>
  <CabecalhoDePagina
    titulo="Insumos"
    descricao="Produtos em estoque: quantidade atual, mínimo, validade e histórico de consumo."
  />
  <EstadoVazio
    icone="insumos"
    titulo="Nenhum insumo cadastrado"
    texto="A lista de insumos aparece aqui depois da primeira importação de dados."
  />
</template>
