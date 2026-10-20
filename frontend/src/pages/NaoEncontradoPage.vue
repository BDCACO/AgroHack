<script setup lang="ts">
import IconeSvg from '@/components/IconeSvg.vue'
</script>

<template>
  <section class="max-w-xl animate-surgir pt-4">
    <p class="text-sm text-tinta-3">
      Erro 404
    </p>
    <h1 class="mt-2 font-serif text-[2rem] leading-tight font-medium tracking-[-0.02em] text-tinta">
      Página não encontrada
    </h1>
    <p class="mt-3 text-tinta-2">
      O endereço pode ter mudado, ou o insumo foi removido.
    </p>
    <RouterLink
      :to="{ name: 'painel' }"
      class="botao-secundario group mt-8"
    >
      <IconeSvg
        nome="seta"
        class="size-4 rotate-180 transition-transform duration-200 ease-chegar group-hover:-translate-x-0.5"
      />
      Voltar ao painel
    </RouterLink>
  </section>
</template>
