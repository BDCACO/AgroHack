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
    /** Presente = a rota aparece no menu lateral, com este ícone. `barra`: também na barra de
     * baixo do celular, que só tem lugar para as do dia a dia; as outras ficam em "Mais".
     * `curto` é o rótulo da barra e do "Mais", onde cabem uns 10 caracteres. */
    menu?: { icone: NomeIcone; curto?: string; barra?: boolean }
    /** Tela fora do menu que acende um item dele (o detalhe acende "Insumos"). */
    secao?: string
    /** Só para o dono: some do menu do funcionário, e o endereço digitado leva ao Painel. */
    soDono?: boolean
    /** Só existe com login (usuários, auditoria): com a autenticação desligada, some do menu. */
    comLogin?: boolean
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
const ConfiguracoesPage = () => import('@/pages/ConfiguracoesPage.vue')
const ComprasPage = () => import('@/pages/ComprasPage.vue')
const RelatoriosPage = () => import('@/pages/RelatoriosPage.vue')
const FornecedoresPage = () => import('@/pages/FornecedoresPage.vue')
const FornecedorPage = () => import('@/pages/FornecedorPage.vue')
const UsuariosPage = () => import('@/pages/UsuariosPage.vue')
const AuditoriaPage = () => import('@/pages/AuditoriaPage.vue')
const NaoEncontradoPage = () => import('@/pages/NaoEncontradoPage.vue')
const EntrarPage = () => import('@/pages/EntrarPage.vue')

// Na rota, e não num guarda global: vale também nos roteadores que os testes montam.
// Espera a sessão: aberto direto em /importar, o site ainda não sabe quem é.
const soDono: NavigationGuard = async () => {
  const sessao = useSessaoStore()
  await sessao.iniciar()
  return sessao.podeGerir ? true : { name: 'painel' }
}

// Usuários, conta e auditoria só existem com login: sem ele, quem digita o endereço volta.
const comLogin: NavigationGuard = async () => {
  const sessao = useSessaoStore()
  await sessao.iniciar()
  return sessao.usuario ? true : { name: 'painel' }
}

// As telas do menu. A ORDEM aqui é a ordem do menu — o menu é derivado desta
// lista, então registrar uma tela é um lugar só.
const telas: RouteRecordRaw[] = [
  {
    path: '',
    name: 'painel',
    component: PainelPage,
    meta: { titulo: 'Painel', menu: { icone: 'painel', barra: true } },
  },
  {
    path: 'insumos',
    name: 'insumos',
    component: InsumosPage,
    meta: { titulo: 'Insumos', menu: { icone: 'insumos', barra: true } },
  },
  {
    path: 'movimentacoes',
    name: 'movimentacoes',
    component: MovimentacoesPage,
    meta: { titulo: 'Movimentações', menu: { icone: 'movimentacoes', curto: 'Movimentos', barra: true } },
  },
  {
    path: 'compras',
    name: 'compras',
    component: ComprasPage,
    meta: { titulo: 'Compras', menu: { icone: 'compras', barra: true } },
  },
  {
    path: 'talhoes',
    name: 'talhoes',
    component: TalhoesPage,
    meta: { titulo: 'Talhões', menu: { icone: 'talhoes' } },
  },
  {
    path: 'relatorios',
    name: 'relatorios',
    component: RelatoriosPage,
    meta: { titulo: 'Relatórios', menu: { icone: 'relatorios' } },
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
    path: 'usuarios',
    name: 'usuarios',
    component: UsuariosPage,
    beforeEnter: [comLogin, soDono],
    meta: { titulo: 'Usuários', menu: { icone: 'usuarios' }, soDono: true, comLogin: true },
  },
  {
    path: 'auditoria',
    name: 'auditoria',
    component: AuditoriaPage,
    beforeEnter: [comLogin, soDono],
    meta: { titulo: 'Auditoria', menu: { icone: 'auditoria' }, soDono: true, comLogin: true },
  },
  {
    // O tema, o perfil, a senha, os aparelhos e se a API e o banco estão no ar. Com a
    // autenticação desligada, só o tema e o sistema (não há de quem ser o perfil).
    path: 'configuracoes',
    name: 'configuracoes',
    component: ConfiguracoesPage,
    meta: { titulo: 'Configurações', menu: { icone: 'configuracoes' } },
  },
]

export interface ItemDeMenu {
  nome: string
  soDono: boolean
  comLogin: boolean
  barra: boolean
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
          comLogin: Boolean(tela.meta.comLogin),
          barra: Boolean(tela.meta.menu.barra),
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
        path: 'compras/fornecedores',
        name: 'fornecedores',
        component: FornecedoresPage,
        meta: { titulo: 'Fornecedores', secao: 'compras' },
      },
      {
        path: 'compras/fornecedores/:id(\\d+)',
        name: 'fornecedor',
        component: FornecedorPage,
        props: (rota) => ({ id: Number(rota.params.id) }),
        meta: { titulo: 'Fornecedor', secao: 'compras' },
      },
      // Minha conta e Sistema viraram partes de Configurações: o endereço antigo leva até lá.
      { path: 'conta', redirect: { name: 'configuracoes' } },
      { path: 'sistema', redirect: { name: 'configuracoes' } },
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
