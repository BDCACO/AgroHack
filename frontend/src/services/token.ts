/** O token da sessão, guardado no navegador: vale 30 dias, e o login não pode cair a cada
 * vez que se fecha a aba. Sem armazenamento (aba anônima, site bloqueado), vale só
 * enquanto a página estiver aberta. */
const CHAVE = 'campocerto.token'
let naMemoria: string | null = null

export function lerToken(): string | null {
  try {
    return localStorage.getItem(CHAVE) ?? naMemoria
  } catch {
    return naMemoria
  }
}

export function guardarToken(token: string | null) {
  naMemoria = token
  try {
    if (token === null) localStorage.removeItem(CHAVE)
    else localStorage.setItem(CHAVE, token)
  } catch {
    // Sem armazenamento: fica só na memória.
  }
}
