import { describe, expect, it } from 'vitest'

import { formatarData, formatarQuantidade, hojeIso } from '@/formatos'

describe('formatos', () => {
  it('quantidade no padrão brasileiro, até 3 casas', () => {
    expect(formatarQuantidade(1250.5)).toBe('1.250,5')
    expect(formatarQuantidade(10)).toBe('10')
    expect(formatarQuantidade(0.1234)).toBe('0,123')
  })

  it('data AAAA-MM-DD vira DD/MM/AAAA sem deslocar o dia por fuso', () => {
    expect(formatarData('2026-10-01')).toBe('01/10/2026')
  })

  it('hojeIso usa a data local', () => {
    expect(hojeIso(new Date(2026, 0, 5, 23, 30))).toBe('2026-01-05')
  })
})
