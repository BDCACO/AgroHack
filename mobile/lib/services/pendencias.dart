import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../core/api/cliente_api.dart';
import '../models/api.dart';
import 'estoque.dart';

/// Um lançamento que não conseguiu sair do aparelho ainda.
class Pendencia {
  const Pendencia({required this.criadoEm, required this.dados, this.erro});

  /// Identifica a pendência (não existe id da API: ainda não foi criada lá).
  final DateTime criadoEm;
  final MovimentacaoEntrada dados;

  /// Motivo pelo qual a API recusou o envio. `null` enquanto nunca tentou
  /// ou só faltou rede (nesse caso não é recusa, é só tentar de novo depois).
  final String? erro;

  Pendencia comErro(String? erro) =>
      Pendencia(criadoEm: criadoEm, dados: dados, erro: erro);

  Map<String, dynamic> toJson() => {
    'criado_em': criadoEm.toIso8601String(),
    'dados': dados.toJson(),
    'erro': erro,
  };

  factory Pendencia.fromJson(Map<String, dynamic> json) => Pendencia(
    criadoEm: DateTime.parse(json['criado_em'] as String),
    dados: MovimentacaoEntrada.fromJson(json['dados'] as Map<String, dynamic>),
    erro: json['erro'] as String?,
  );
}

/// Lançamentos feitos sem rede ficam guardados no aparelho até serem
/// enviados com sucesso. Se a API recusar o envio (não por falta de rede),
/// a pendência fica visível com o motivo, para a pessoa decidir: tentar de
/// novo ou descartar.
class PendenciasService {
  const PendenciasService(this._estoque);

  final EstoqueService _estoque;
  static const _chave = 'pendencias_movimentacoes';

  Future<List<Pendencia>> listar() async {
    final prefs = await SharedPreferences.getInstance();
    final bruto = prefs.getString(_chave);
    if (bruto == null) return [];
    return [
      for (final item in jsonDecode(bruto) as List)
        Pendencia.fromJson(item as Map<String, dynamic>),
    ];
  }

  Future<void> adicionar(MovimentacaoEntrada dados) async {
    final pendencias = await listar()
      ..add(Pendencia(criadoEm: DateTime.now(), dados: dados));
    await _salvar(pendencias);
  }

  Future<void> descartar(DateTime criadoEm) async {
    final pendencias = await listar()
      ..removeWhere((p) => p.criadoEm == criadoEm);
    await _salvar(pendencias);
  }

  /// Tenta enviar as pendências (ou só uma, se `apenas` for informado).
  /// Para na primeira sem resposta da API — ainda sem rede, tenta de novo
  /// depois — e marca as que a API recusou com o motivo.
  Future<void> tentarEnviar({DateTime? apenas}) async {
    final pendencias = await listar();
    if (pendencias.isEmpty) return;
    final restantes = <Pendencia>[];
    var semRede = false;
    for (final pendencia in pendencias) {
      if (semRede || (apenas != null && pendencia.criadoEm != apenas)) {
        restantes.add(pendencia);
        continue;
      }
      try {
        await _estoque.registrarMovimentacao(pendencia.dados);
      } catch (erro) {
        if (erro is ApiError && erro.status != null) {
          restantes.add(pendencia.comErro(erro.mensagem));
        } else {
          semRede = true;
          restantes.add(pendencia);
        }
      }
    }
    await _salvar(restantes);
  }

  Future<void> _salvar(List<Pendencia> pendencias) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      _chave,
      jsonEncode([for (final p in pendencias) p.toJson()]),
    );
  }
}
