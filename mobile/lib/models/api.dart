// Espelho dos schemas da API, como o frontend/src/types/api.ts do site.
// Escrito à mão: mudou um schema no backend, muda aqui e lá.

typedef Json = Map<String, dynamic>;

double _numero(Object? valor) => (valor as num).toDouble();
double? _numeroOuNulo(Object? valor) => (valor as num?)?.toDouble();

/// Datas da API vêm como AAAA-MM-DD, sem hora.
DateTime _data(Object? valor) => DateTime.parse(valor as String);
DateTime? _dataOuNula(Object? valor) =>
    valor == null ? null : DateTime.parse(valor as String);

String _textoDeData(DateTime data) =>
    '${data.year.toString().padLeft(4, '0')}-'
    '${data.month.toString().padLeft(2, '0')}-'
    '${data.day.toString().padLeft(2, '0')}';

class ReadinessResponse {
  const ReadinessResponse({required this.pronto, required this.bancoOk});

  factory ReadinessResponse.fromJson(Json json) => ReadinessResponse(
    pronto: json['status'] == 'pronto',
    bancoOk: json['database'] == 'ok',
  );

  final bool pronto;
  final bool bancoOk;
}

enum Gravidade {
  alta,
  media,
  baixa;

  static Gravidade fromJson(Object? valor) => values.byName(valor as String);
}

enum TipoAlerta {
  abaixoDoMinimo('abaixo_do_minimo'),
  riscoDeFalta('risco_de_falta'),
  vencido('vencido'),
  vencimentoProximo('vencimento_proximo'),
  excesso('excesso'),
  baixaMovimentacao('baixa_movimentacao'),
  consumoIncomum('consumo_incomum');

  const TipoAlerta(this.valor);

  final String valor;

  static TipoAlerta fromJson(Object? valor) =>
      values.firstWhere((tipo) => tipo.valor == valor);
}

class Alerta {
  const Alerta({
    required this.tipo,
    required this.gravidade,
    required this.justificativa,
  });

  factory Alerta.fromJson(Json json) => Alerta(
    tipo: TipoAlerta.fromJson(json['tipo']),
    gravidade: Gravidade.fromJson(json['gravidade']),
    justificativa: json['justificativa'] as String,
  );

  final TipoAlerta tipo;
  final Gravidade gravidade;
  final String justificativa;
}

class Reposicao {
  const Reposicao({
    required this.pedirEm,
    required this.pedirHoje,
    required this.quantidade,
    required this.justificativa,
  });

  factory Reposicao.fromJson(Json json) => Reposicao(
    pedirEm: _data(json['pedir_em']),
    pedirHoje:
        json['pedir_hoje'] as bool, // decidido pela API, na data de Rondônia
    quantidade: _numero(json['quantidade']),
    justificativa: json['justificativa'] as String,
  );

  final DateTime pedirEm;
  final bool pedirHoje;
  final double quantidade;
  final String justificativa;
}

class Analise {
  const Analise({
    required this.consumoDiario,
    required this.coberturaDias,
    required this.alertas,
    required this.reposicao,
    required this.limitacoes,
  });

  factory Analise.fromJson(Json json) => Analise(
    consumoDiario: _numeroOuNulo(json['consumo_diario']),
    coberturaDias: _numeroOuNulo(json['cobertura_dias']),
    alertas: [
      for (final alerta in json['alertas'] as List)
        Alerta.fromJson(alerta as Json),
    ],
    reposicao: json['reposicao'] == null
        ? null
        : Reposicao.fromJson(json['reposicao'] as Json),
    limitacoes: List<String>.from(json['limitacoes'] as List),
  );

  final double? consumoDiario;
  final double? coberturaDias;
  final List<Alerta> alertas;
  final Reposicao? reposicao;
  final List<String> limitacoes;
}

class InsumoCadastro {
  const InsumoCadastro({
    required this.nome,
    required this.unidade,
    this.estoqueMinimo,
    this.prazoReposicaoDias,
    this.codigoDeBarras,
  });

  final String nome;
  final String unidade;
  final double? estoqueMinimo;
  final int? prazoReposicaoDias;
  final String? codigoDeBarras;

  Json toJson() => {
    'nome': nome,
    'unidade': unidade,
    'estoque_minimo': estoqueMinimo,
    'prazo_reposicao_dias': prazoReposicaoDias,
    // Omitido quando nulo: um PUT sem o campo mantém o código já vinculado
    // (a API só o substitui quando a chave vem no corpo).
    if (codigoDeBarras != null) 'codigo_de_barras': codigoDeBarras,
  };
}

class Insumo extends InsumoCadastro {
  const Insumo({
    required this.id,
    required super.nome,
    required super.unidade,
    super.estoqueMinimo,
    super.prazoReposicaoDias,
    super.codigoDeBarras,
    required this.demonstracao,
    required this.estoqueAtual,
    required this.analise,
  });

  factory Insumo.fromJson(Json json) => Insumo(
    id: json['id'] as int,
    nome: json['nome'] as String,
    unidade: json['unidade'] as String,
    estoqueMinimo: _numeroOuNulo(json['estoque_minimo']),
    prazoReposicaoDias: json['prazo_reposicao_dias'] as int?,
    codigoDeBarras: json['codigo_de_barras'] as String?,
    demonstracao:
        json['demonstracao'] as bool, // gerado por `make demo`: não é dado real
    estoqueAtual: _numero(json['estoque_atual']),
    analise: Analise.fromJson(json['analise'] as Json),
  );

  final int id;
  final bool demonstracao;
  final double estoqueAtual;
  final Analise analise;
}

enum TipoMovimentacao {
  entrada,
  saida;

  static TipoMovimentacao fromJson(Object? valor) =>
      values.byName(valor as String);
}

class MovimentacaoEntrada {
  const MovimentacaoEntrada({
    required this.insumoId,
    required this.tipo,
    required this.data,
    required this.quantidade,
    this.validade,
  });

  // Espelha toJson: usado para guardar um lançamento sem rede no aparelho.
  factory MovimentacaoEntrada.fromJson(Json json) => MovimentacaoEntrada(
    insumoId: json['insumo_id'] as int,
    tipo: TipoMovimentacao.fromJson(json['tipo']),
    data: _data(json['data']),
    quantidade: _numero(json['quantidade']),
    validade: _dataOuNula(json['validade']),
  );

  final int insumoId;
  final TipoMovimentacao tipo;
  final DateTime data;
  final double quantidade;
  final DateTime? validade;

  Json toJson() => {
    'insumo_id': insumoId,
    'tipo': tipo.name,
    'data': _textoDeData(data),
    'quantidade': quantidade,
    'validade': validade == null ? null : _textoDeData(validade!),
  };
}

class Movimentacao extends MovimentacaoEntrada {
  const Movimentacao({
    required this.id,
    required super.insumoId,
    required super.tipo,
    required super.data,
    required super.quantidade,
    super.validade,
  });

  factory Movimentacao.fromJson(Json json) => Movimentacao(
    id: json['id'] as int,
    insumoId: json['insumo_id'] as int,
    tipo: TipoMovimentacao.fromJson(json['tipo']),
    data: _data(json['data']),
    quantidade: _numero(json['quantidade']),
    validade: _dataOuNula(json['validade']),
  );

  final int id;
}

class PontoDeEstoque {
  const PontoDeEstoque({required this.data, required this.saldo});

  factory PontoDeEstoque.fromJson(Json json) =>
      PontoDeEstoque(data: _data(json['data']), saldo: _numero(json['saldo']));

  final DateTime data;
  final double saldo; // no fim do dia
}

class InsumoDetalhe {
  const InsumoDetalhe({
    required this.insumo,
    required this.historico,
    required this.movimentacoes,
  });

  factory InsumoDetalhe.fromJson(Json json) => InsumoDetalhe(
    insumo: Insumo.fromJson(json),
    historico: [
      for (final ponto in json['historico'] as List)
        PontoDeEstoque.fromJson(ponto as Json),
    ],
    movimentacoes: [
      for (final mov in json['movimentacoes'] as List)
        Movimentacao.fromJson(mov as Json),
    ],
  );

  final Insumo insumo;
  final List<PontoDeEstoque>
  historico; // um ponto por dia com movimentação, do mais antigo
  final List<Movimentacao> movimentacoes; // as mais recentes primeiro
}

class Usuario {
  const Usuario({
    required this.id,
    required this.nome,
    required this.login,
    required this.papel,
  });

  factory Usuario.fromJson(Json json) => Usuario(
    id: json['id'] as int,
    nome: json['nome'] as String,
    login: json['login'] as String,
    papel: json['papel'] as String,
  );

  final int id;
  final String nome;
  final String login;
  final String papel; // "dono" ou "funcionario"
}

/// O que `POST /auth/entrar` devolve: o token da sessão e quem entrou.
class Entrada {
  const Entrada({required this.token, required this.usuario});

  factory Entrada.fromJson(Json json) => Entrada(
    token: json['token'] as String,
    usuario: Usuario.fromJson(json['usuario'] as Json),
  );

  final String token;
  final Usuario usuario;
}
