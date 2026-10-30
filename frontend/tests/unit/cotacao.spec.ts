import { describe, expect, it } from 'vitest'

import { mensagemDeCotacao } from '@/cotacao'
import type { Insumo, Reposicao } from '@/types/api'

const HOJE = new Date('2026-10-29T12:00:00')

function insumo(parciais: Partial<Insumo> = {}): Insumo {
  return {
    id: 1,
    nome: 'Ureia',
    unidade: 'kg',
    estoque_minimo: null,
    prazo_reposicao_dias: null,
    embalagem: null,
    pedido_minimo: null,
    carencia_dias: null,
    marcas_preferenciais: null,
    custo_medio: null,
    valor_em_estoque: null,
    demonstracao: false,
    estoque_atual: 10,
    analise: { consumo_diario: 1, cobertura_dias: 7, alertas: [], reposicao: null, limitacoes: [] },
    ...parciais,
  }
}

function item(insumoParcial: Partial<Insumo>, reposicaoParcial: Partial<Reposicao> = {}) {
  return {
    insumo: insumo(insumoParcial),
    pedir_em: '2026-10-29',
    pedir_hoje: true,
    quantidade: 300,
    justificativa: '',
    custo_estimado: null,
    ...reposicaoParcial,
  }
}

describe('mensagemDeCotacao', () => {
  it('sem marca cadastrada, pede qualquer marca equivalente', () => {
    const mensagem = mensagemDeCotacao([item({})], HOJE)

    expect(mensagem).toContain('Qualquer marca/similar equivalente')
  })

  it('com marca cadastrada, pede a marca de preferência', () => {
    const mensagem = mensagemDeCotacao([item({ marcas_preferenciais: 'Yara, Heringer' })], HOJE)

    expect(mensagem).toContain('Marca: Yara, Heringer')
    expect(mensagem).not.toContain('Qualquer marca')
  })

  it('com embalagem, diz quantas fecham a quantidade pedida', () => {
    const mensagem = mensagemDeCotacao([item({ embalagem: 50 })], HOJE)

    expect(mensagem).toContain('(6 embalagens de 50 kg)')
  })

  it('usa a cobertura de dias como data limite de entrega', () => {
    const mensagem = mensagemDeCotacao([item({})], HOJE)

    // cobertura_dias: 7, a partir de 29/10/2026 cai em 05/11/2026.
    expect(mensagem).toContain('Entregar até 05/11/2026');
  })

  it('sem cobertura calculável, não inventa uma data de entrega', () => {
    const mensagem = mensagemDeCotacao(
      [item({ analise: { consumo_diario: null, cobertura_dias: null, alertas: [], reposicao: null, limitacoes: [] } })],
      HOJE,
    )

    expect(mensagem).not.toContain('Entregar até')
  })
})
