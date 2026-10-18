import { createRouter, createWebHistory } from 'vue-router'

import AppLayout from '@/layouts/AppLayout.vue'
import InicioPage from '@/pages/InicioPage.vue'

// Páginas além da inicial entram como import dinâmico (chunk próprio), como no
// ArkoHub: cada tela só é baixada quando alguém navega até ela.
const NaoEncontradoPage = () => import('@/pages/NaoEncontradoPage.vue')

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: AppLayout,
      children: [
        { path: '', name: 'inicio', component: InicioPage, meta: { titulo: 'Início' } },
        {
          path: ':caminho(.*)*',
          name: 'nao-encontrado',
          component: NaoEncontradoPage,
          meta: { titulo: 'Página não encontrada' },
        },
      ],
    },
  ],
})

router.afterEach((rota) => {
  const titulo = rota.meta.titulo
  document.title = typeof titulo === 'string' ? `${titulo} · CampoCerto` : 'CampoCerto'
})
