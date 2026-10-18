<script setup lang="ts">
import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
</script>

<template>
  <CabecalhoDePagina
    titulo="Importar dados"
    descricao="Envie os registros de compras, retiradas e estoque para atualizar as análises."
  />
  <!-- O formulário de envio entra quando o formato dos arquivos da organização
       for conhecido — não presumimos colunas nem tipo de arquivo. -->
  <EstadoVazio
    icone="importar"
    titulo="Importação em preparação"
    texto="Os formatos aceitos serão definidos a partir dos arquivos fornecidos pela organização do desafio."
  />
</template>
