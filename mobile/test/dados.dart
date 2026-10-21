// Respostas da API no formato que ela manda, para os testes.

const insumoComAlerta = <String, dynamic>{
  'id': 1,
  'nome': 'Ureia',
  'unidade': 'kg',
  'estoque_minimo': 200,
  'prazo_reposicao_dias': 15,
  'demonstracao': false,
  'estoque_atual': 120,
  'analise': {
    'consumo_diario': 4.5,
    'cobertura_dias': 26.7,
    'alertas': [
      {
        'tipo': 'abaixo_do_minimo',
        'gravidade': 'alta',
        'justificativa': 'Estoque de 120 kg, abaixo do mínimo de 200 kg.',
      },
    ],
    'reposicao': {
      'pedir_em': '2026-10-25',
      'pedir_hoje': false,
      'quantidade': 300,
      'justificativa': 'Cobre 60 dias de consumo.',
    },
    'limitacoes': ['Poucas saídas registradas.'],
  },
};

const insumoSemAlerta = <String, dynamic>{
  'id': 2,
  'nome': 'Calcário',
  'unidade': 't',
  'estoque_minimo': null,
  'prazo_reposicao_dias': null,
  'demonstracao': true,
  'estoque_atual': 1500,
  'analise': {
    'consumo_diario': null,
    'cobertura_dias': null,
    'alertas': <Object>[],
    'reposicao': null,
    'limitacoes': <Object>[],
  },
};

const movimentacao = <String, dynamic>{
  'id': 10,
  'insumo_id': 1,
  'tipo': 'saida',
  'data': '2026-10-20',
  'quantidade': 30,
  'validade': null,
};
