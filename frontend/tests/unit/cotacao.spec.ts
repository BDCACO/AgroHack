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
    embalagens: null,
    entregar_ate: '2026-11-05',
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

  it('com embalagem, usa o número de embalagens que a API calculou', () => {
    // 1,1 L em frascos de 0,1 L: a divisão no navegador daria 12 (11,000000000000002).
    const mensagem = mensagemDeCotacao(
      [item({ unidade: 'L', embalagem: 0.1 }, { quantidade: 1.1, embalagens: 11 })],
      HOJE,
    )

    expect(mensagem).toContain('1,1 L (11 embalagens de 0,1 L)')
  })

  it('uma embalagem só vai no singular', () => {
    const mensagem = mensagemDeCotacao([item({ embalagem: 300 }, { embalagens: 1 })], HOJE)

    expect(mensagem).toContain('(1 embalagem de 300 kg)')
  })

  it('o prazo de entrega é o da API, não a cobertura somada ao relógio do navegador', () => {
    // Cobertura de 6,5 dias às 23h: somada ao relógio cairia em 05/11; a API diz 04/11.
    const mensagem = mensagemDeCotacao(
      [
        item(
          { analise: { consumo_diario: 1, cobertura_dias: 6.5, alertas: [], reposicao: null, limitacoes: [] } },
          { entregar_ate: '2026-11-04' },
        ),
      ],
      new Date('2026-10-29T23:00:00'),
    )

    expect(mensagem).toContain('Entregar até 04/11/2026')
  })
})
