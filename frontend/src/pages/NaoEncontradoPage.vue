<template>
  <section class="space-y-3">
    <h1 class="text-2xl font-semibold text-campo-900">
      Página não encontrada
    </h1>
    <RouterLink
      :to="{ name: 'inicio' }"
      class="text-campo-700 underline"
    >
      Voltar ao início
    </RouterLink>
  </section>
</template>
