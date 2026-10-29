import { ref } from 'vue'

// O título da página aparece só na barra do topo (e no cabeçalho do celular), e não dentro
// dela. Quem o conhece é a página (o nome do insumo, do talhão), não a rota: o
// CabecalhoDePagina o publica aqui, com o caminho em que foi montado. Na troca de página,
// a que sai ainda está montada por um instante: o caminho diz que o título não é mais dela.
export const tituloDaPagina = ref<{ caminho: string; titulo: string } | null>(null)
