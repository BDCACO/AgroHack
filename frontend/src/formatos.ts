/** Dinheiro no padrão brasileiro: R$ 1.234,50. Quem calcula é a API; aqui só se formata. */
export const reais = (valor: number) =>
  valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
