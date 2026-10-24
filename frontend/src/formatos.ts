// Formatação para exibição, no padrão brasileiro. Só apresentação: nenhum
// cálculo de negócio mora aqui.

const numero = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 3 })

/** 1250.5 → "1.250,5" */
export function formatarQuantidade(valor: number): string {
  return numero.format(valor)
}

/** "2026-10-01" → "01/10/2026". Sem `new Date()`: a data da API não tem fuso,
 * e convertê-la para Date em UTC-4 a mostraria um dia antes. */
export function formatarData(iso: string): string {
  const [ano, mes, dia] = iso.split('-')
  return `${dia}/${mes}/${ano}`
}

/** Data local de hoje no formato do <input type="date">. */
export function hojeIso(agora: Date = new Date()): string {
  const mes = String(agora.getMonth() + 1).padStart(2, '0')
  const dia = String(agora.getDate()).padStart(2, '0')
  return `${agora.getFullYear()}-${mes}-${dia}`
}
