<script setup lang="ts">
import IconeSvg from '@/components/IconeSvg.vue'
</script>

<template>
  <section class="cartao flex animate-surgir flex-col items-center px-6 py-16 text-center">
    <p
      class="text-6xl font-bold tracking-tight text-campo-500"
      aria-hidden="true"
    >
      404
    </p>
    <h1 class="mt-2 text-2xl font-bold text-campo-950">
      Página não encontrada
    </h1>
    <p class="mt-1.5 max-w-sm text-sm text-stone-600">
      O endereço pode ter mudado, ou o insumo foi removido.
    </p>
    <RouterLink
      :to="{ name: 'painel' }"
      class="botao-primario group mt-6"
    >
      <IconeSvg
        nome="seta"
        class="h-4 w-4 rotate-180 transition-transform duration-200 group-hover:-translate-x-0.5"
      />
      Voltar ao painel
    </RouterLink>
  </section>
</template>
