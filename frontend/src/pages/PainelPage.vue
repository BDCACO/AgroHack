<script setup lang="ts">
import CabecalhoDePagina from '@/components/CabecalhoDePagina.vue'
import EstadoVazio from '@/components/EstadoVazio.vue'
import IconeSvg from '@/components/IconeSvg.vue'

// As situações que o CampoCerto vai identificar (requisitos do desafio). Isto é
// TEXTO DE TELA, não regra: quem decide se um insumo está em cada situação é a
// análise do backend. Quando ela existir, esta lista passa a vir da API com a
// contagem e a justificativa de cada alerta.
const situacoes = [
  { titulo: 'Estoque abaixo do mínimo', texto: 'Insumos com quantidade menor que o mínimo definido.' },
  { titulo: 'Risco de falta', texto: 'Insumos que podem acabar antes da próxima reposição, pelo ritmo de consumo.' },
  { titulo: 'Próximos do vencimento', texto: 'Lotes que vencem em breve.' },
  { titulo: 'Excesso de estoque', texto: 'Quantidade acima do que o consumo justifica.' },
  { titulo: 'Baixa movimentação', texto: 'Insumos parados há muito tempo.' },
  { titulo: 'Consumo incomum', texto: 'Retiradas fora do padrão histórico.' },
  { titulo: 'Reposição estimada', texto: 'Quanto e quando comprar, com as limitações da estimativa.' },
]
</script>

<template>
  <CabecalhoDePagina
    titulo="Painel"
    descricao="Alertas sobre o estoque de insumos, com a justificativa de cada um."
  />

  <EstadoVazio
    icone="importar"
    titulo="Nenhum dado de estoque ainda"
    texto="Os alertas aparecem aqui depois que os registros de compras, retiradas e estoque forem importados."
  >
    <RouterLink
      :to="{ name: 'importar' }"
      class="inline-flex items-center gap-2 rounded-md bg-campo-600 px-4 py-2 text-sm font-medium text-white hover:bg-campo-700"
    >
      Importar dados
    </RouterLink>
  </EstadoVazio>

  <section aria-labelledby="titulo-situacoes">
    <h2
      id="titulo-situacoes"
      class="text-sm font-semibold uppercase tracking-wide text-stone-500"
    >
      O que será analisado
    </h2>
    <ul class="mt-3 grid overflow-hidden rounded-lg border border-stone-200 bg-white sm:grid-cols-2 lg:grid-cols-3">
      <li
        v-for="situacao in situacoes"
        :key="situacao.titulo"
        class="-mr-px -mb-px flex gap-3 border-r border-b border-stone-200 p-4"
      >
        <IconeSvg
          nome="alerta"
          class="mt-0.5 h-5 w-5 shrink-0 text-stone-300"
        />
        <div>
          <p class="font-medium text-stone-800">
            {{ situacao.titulo }}
          </p>
          <p class="mt-0.5 text-sm text-stone-500">
            {{ situacao.texto }}
          </p>
          <p class="mt-2 text-xs font-medium text-stone-400">
            Aguardando dados
          </p>
        </div>
      </li>
    </ul>
  </section>
</template>
