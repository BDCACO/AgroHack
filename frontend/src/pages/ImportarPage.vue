<script setup lang="ts">
import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
</script>

<template>
  <CabecalhoDePagina
    titulo="Importar dados"
    descricao="Carregar de uma vez o histórico de compras e retiradas que já está numa planilha."
  />
  <!-- A organização não forneceu arquivos de dados: o modelo de planilha será nosso, e
       só entra se der tempo (docs/ARQUITETURA.md, "Próximas decisões"). -->
  <EstadoVazio
    icone="importar"
    titulo="Importação de planilha ainda não disponível"
    texto="Por enquanto, lance as compras e retiradas na tela de Movimentações."
  >
    <RouterLink
      :to="{ name: 'movimentacoes' }"
      class="inline-flex rounded-md bg-campo-600 px-4 py-2 text-sm font-medium text-white hover:bg-campo-700"
    >
      Ir para Movimentações
    </RouterLink>
  </EstadoVazio>
</template>
