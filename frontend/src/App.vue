<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { definirAoPerderSessao } from '@/services/http'
import { useSessaoStore } from '@/stores/sessao'

const sessao = useSessaoStore()
const router = useRouter()

// A API respondeu 401 (falta o login, ou a sessão venceu ou foi encerrada): a sessão deste
// navegador acabou. Leva à entrada, e de lá de volta para onde se estava.
definirAoPerderSessao(() => {
  sessao.limpar()
  const atual = router.currentRoute.value
  if (atual.name === 'entrar') return
  router.replace({ name: 'entrar', query: { volta: atual.fullPath } })
})
onBeforeUnmount(() => definirAoPerderSessao(null))
onMounted(() => sessao.iniciar())
</script>

<template>
  <RouterView />
</template>
