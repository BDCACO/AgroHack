/** Dinheiro no padrão brasileiro: R$ 1.234,50. Quem calcula é a API; aqui só se formata. */
export const reais = (valor: number) =>
  valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })

/** Data e hora de um instante da API (ISO com fuso), no fuso do navegador: 27/10/2026 14:05. */
export const dataHora = (instante: string) =>
  new Date(instante).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })

/** AAAA-MM-DD da API como o produtor lê: 27/10/2026. */
export const dataBr = (data: string) => data.split('-').reverse().join('/')

/** Há quanto tempo, em palavras: "agora há pouco", "há 3 h", "há 2 dias". */
export function haQuanto(instante: string, agora = Date.now()): string {
  const minutos = Math.max(0, Math.round((agora - new Date(instante).getTime()) / 60_000))
  if (minutos < 10) return 'agora há pouco'
  if (minutos < 60) return `há ${minutos} min`
  const horas = Math.round(minutos / 60)
  if (horas < 24) return `há ${horas} h`
  const dias = Math.round(horas / 24)
  return dias === 1 ? 'ontem' : `há ${dias} dias`
}
