import { computed, readonly, ref, watchEffect } from 'vue'

// Claro, escuro ou igual ao aparelho (o que o celular ou o computador estiver usando). A
// escolha é deste navegador, como o menu recolhido; sem armazenamento, começa no claro. O
// index.html aplica a escolha antes de a página aparecer, para não piscar branco; daqui em
// diante, é este módulo que muda o `data-tema` da página.
export type Tema = 'claro' | 'escuro' | 'sistema'

const CHAVE = 'campocerto.tema'

function ler(): Tema {
  try {
    const guardado = localStorage.getItem(CHAVE)
    return guardado === 'escuro' || guardado === 'sistema' ? guardado : 'claro'
  } catch {
    return 'claro'
  }
}

const escolhido = ref<Tema>(ler())
const midia = typeof window !== 'undefined' ? window.matchMedia?.('(prefers-color-scheme: dark)') : undefined
const aparelhoEscuro = ref(midia?.matches ?? false)
midia?.addEventListener?.('change', (evento) => (aparelhoEscuro.value = evento.matches))

export const temaEscolhido = readonly(escolhido)
/** O que está na tela agora: com "igual ao aparelho", o do aparelho. */
export const temaAplicado = computed<'claro' | 'escuro'>(() =>
  escolhido.value === 'sistema' ? (aparelhoEscuro.value ? 'escuro' : 'claro') : escolhido.value,
)

watchEffect(() => {
  if (typeof document !== 'undefined') document.documentElement.dataset.tema = temaAplicado.value
})

export function escolherTema(tema: Tema) {
  escolhido.value = tema
  try {
    localStorage.setItem(CHAVE, tema)
  } catch {
    // Sem armazenamento, vale só até recarregar.
  }
}

/** As cores de letra e de grade dos gráficos (o ECharts não lê CSS): as do stone de cada tema. */
export const coresDoGrafico = computed(() =>
  temaAplicado.value === 'escuro'
    ? { tinta: '#b8b2ac', tintaSuave: '#a19a94', grade: '#3a3633' }
    : { tinta: '#57534e', tintaSuave: '#78716c', grade: '#e7e5e4' },
)
