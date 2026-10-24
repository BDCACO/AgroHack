import {
  createRouter,
  createWebHistory,
  type NavigationGuard,
  type RouteRecordRaw,
} from 'vue-router'

import type { NomeIcone } from '@/components/IconeSvg.vue'
import AppLayout from '@/layouts/AppLayout.vue'
import PainelPage from '@/pages/PainelPage.vue'
import { useSessaoStore } from '@/stores/sessao'

declare module 'vue-router' {
  interface RouteMeta {
    titulo?: string
    /** Presente = a rota aparece no menu lateral e na barra de baixo do celular, com este
     * ícone. `curto` é o rótulo da barra de baixo, onde cabem uns 10 caracteres. */
    menu?: { icone: NomeIcone; curto?: string }
    /** Tela fora do menu que acende um item dele (o detalhe acende "Insumos"). */
    secao?: string
    /** Só para o dono: some do menu do funcionário, e o endereço digitado leva ao Painel. */
    soDono?: boolean
  }
}

// Páginas além do Painel entram como import dinâmico (chunk próprio), como no
// ArkoHub: cada tela só é baixada quando alguém navega até ela.
const InsumosPage = () => import('@/pages/InsumosPage.vue')
const InsumoPage = () => import('@/pages/InsumoPage.vue')
const MovimentacoesPage = () => import('@/pages/MovimentacoesPage.vue')
const TalhoesPage = () => import('@/pages/TalhoesPage.vue')
const TalhaoPage = () => import('@/pages/TalhaoPage.vue')
const ImportarPage = () => import('@/pages/ImportarPage.vue')
const SistemaPage = () => import('@/pages/SistemaPage.vue')
const NaoEncontradoPage = () => import('@/pages/NaoEncontradoPage.vue')
const EntrarPage = () => import('@/pages/EntrarPage.vue')

// Na rota, e não num guarda global: vale também nos roteadores que os testes montam.
// Espera a sessão: aberto direto em /importar, o site ainda não sabe quem é.
const soDono: NavigationGuard = async () => {
  const sessao = useSessaoStore()
  await sessao.iniciar()
  return sessao.podeGerir ? true : { name: 'painel' }
}

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
    meta: { titulo: 'Movimentações', menu: { icone: 'movimentacoes', curto: 'Movimentos' } },
  },
  {
    path: 'talhoes',
    name: 'talhoes',
    component: TalhoesPage,
    meta: { titulo: 'Talhões', menu: { icone: 'talhoes' } },
  },
  {
    path: 'importar',
    name: 'importar',
    component: ImportarPage,
    beforeEnter: soDono,
    meta: {
      titulo: 'Importar dados',
      menu: { icone: 'importar', curto: 'Importar' },
      soDono: true,
    },
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
  soDono: boolean
  rotulo: string
  rotuloCurto: string
  icone: NomeIcone
}

export const itensDeMenu: ItemDeMenu[] = telas.flatMap((tela) =>
  tela.meta?.menu && typeof tela.name === 'string'
    ? [
        {
          nome: tela.name,
          soDono: Boolean(tela.meta.soDono),
          rotulo: tela.meta.titulo ?? tela.name,
          rotuloCurto: tela.meta.menu.curto ?? tela.meta.titulo ?? tela.name,
          icone: tela.meta.menu.icone,
        },
      ]
    : [],
)

export const routes: RouteRecordRaw[] = [
  // Fora do layout: sem menu, porque ainda não se sabe o que a pessoa pode ver.
  { path: '/entrar', name: 'entrar', component: EntrarPage, meta: { titulo: 'Entrar' } },
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
        path: 'talhoes/:id(\\d+)',
        name: 'talhao',
        component: TalhaoPage,
        props: (rota) => ({ id: Number(rota.params.id) }),
        meta: { titulo: 'Talhão', secao: 'talhoes' },
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
  // Tela nova começa do topo; voltar (botão do celular) devolve a rolagem de onde se estava.
  scrollBehavior: (_para, _de, salva) => salva ?? { top: 0 },
})

router.afterEach((rota) => {
  const titulo = rota.meta.titulo
  document.title = titulo ? `${titulo} · CampoCerto` : 'CampoCerto'
})
