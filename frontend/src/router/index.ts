import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import type { NomeIcone } from '@/components/IconeSvg.vue'
import AppLayout from '@/layouts/AppLayout.vue'
import PainelPage from '@/pages/PainelPage.vue'

declare module 'vue-router' {
  interface RouteMeta {
    titulo?: string
    /** Presente = a rota aparece no menu lateral, com este ícone. */
    menu?: { icone: NomeIcone }
    /** Tela fora do menu que acende um item dele (o detalhe acende "Insumos"). */
    secao?: string
  }
}

// Páginas além do Painel entram como import dinâmico (chunk próprio), como no
// ArkoHub: cada tela só é baixada quando alguém navega até ela.
const InsumosPage = () => import('@/pages/InsumosPage.vue')
const InsumoPage = () => import('@/pages/InsumoPage.vue')
const MovimentacoesPage = () => import('@/pages/MovimentacoesPage.vue')
const ImportarPage = () => import('@/pages/ImportarPage.vue')
const SistemaPage = () => import('@/pages/SistemaPage.vue')
const NaoEncontradoPage = () => import('@/pages/NaoEncontradoPage.vue')

// As telas do menu. A ORDEM aqui é a ordem do menu — o menu é derivado desta
// lista, então registrar uma tela é um lugar só.
const telas: RouteRecordRaw[] = [
  {
    path: '',
    name: 'painel',
    component: PainelPage,
    meta: { titulo: 'Painel', menu: { icone: 'painel' } },
  },
  {
    path: 'insumos',
    name: 'insumos',
    component: InsumosPage,
    meta: { titulo: 'Insumos', menu: { icone: 'insumos' } },
  },
  {
    path: 'movimentacoes',
    name: 'movimentacoes',
    component: MovimentacoesPage,
    meta: { titulo: 'Movimentações', menu: { icone: 'movimentacoes' } },
  },
  {
    path: 'importar',
    name: 'importar',
    component: ImportarPage,
    meta: { titulo: 'Importar dados', menu: { icone: 'importar' } },
  },
  {
    path: 'sistema',
    name: 'sistema',
    component: SistemaPage,
    meta: { titulo: 'Sistema', menu: { icone: 'sistema' } },
  },
]

export interface ItemDeMenu {
  nome: string
  rotulo: string
  icone: NomeIcone
}

export const itensDeMenu: ItemDeMenu[] = telas.flatMap((tela) =>
  tela.meta?.menu && typeof tela.name === 'string'
    ? [{ nome: tela.name, rotulo: tela.meta.titulo ?? tela.name, icone: tela.meta.menu.icone }]
    : [],
)

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: AppLayout,
    children: [
      ...telas,
      {
        path: 'insumos/:id(\\d+)',
        name: 'insumo',
        component: InsumoPage,
        props: (rota) => ({ id: Number(rota.params.id) }),
        meta: { titulo: 'Insumo', secao: 'insumos' },
      },
      {
        path: ':caminho(.*)*',
        name: 'nao-encontrado',
        component: NaoEncontradoPage,
        meta: { titulo: 'Página não encontrada' },
      },
    ],
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((rota) => {
  const titulo = rota.meta.titulo
  document.title = titulo ? `${titulo} · CampoCerto` : 'CampoCerto'
})
