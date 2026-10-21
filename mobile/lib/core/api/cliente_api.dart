import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../config.dart';

/// Erro de chamada à API, já normalizado: quem chama não lida com exceção de
/// rede nem com `http.Response`. Mesmo papel do `ApiError` do site.
class ApiError implements Exception {
  const ApiError(this.status, [this.detail]);

  /// `null` = a API não respondeu (rede caiu, timeout, endereço errado).
  final int? status;
  final Object? detail;

  /// Frase para mostrar na tela: a que a API escreveu (409, 404...), quando há
  /// uma. Erro de validação (422) vem como lista técnica do Pydantic, que não
  /// serve ao usuário.
  String get mensagem {
    if (status == null) {
      return 'Sem resposta do servidor. Tente de novo em instantes.';
    }
    final corpo = detail;
    if (corpo is Map && corpo['detail'] is String) {
      return corpo['detail'] as String;
    }
    return 'Não foi possível concluir. Confira os dados.';
  }

  @override
  String toString() => status == null
      ? 'ApiError: a API não respondeu'
      : 'ApiError: a API respondeu $status';
}

/// Cliente HTTP único do app. Nenhuma tela chama `http` direto.
class ClienteApi {
  ClienteApi({http.Client? client, String? baseUrl})
    : _client = client ?? http.Client(),
      _baseUrl = baseUrl ?? urlDaApi;

  final http.Client _client;
  final String _baseUrl;

  static const _timeout = Duration(seconds: 10);

  Future<Object?> get(String caminho, {Set<int> aceitos = const {200}}) =>
      _enviar(() => _client.get(_uri(caminho)), aceitos);

  Future<Object?> post(String caminho, Object corpo) => _enviar(
    () => _client.post(_uri(caminho), headers: _json, body: jsonEncode(corpo)),
    const {200, 201},
  );

  Future<Object?> put(String caminho, Object corpo) => _enviar(
    () => _client.put(_uri(caminho), headers: _json, body: jsonEncode(corpo)),
    const {200},
  );

  Future<void> delete(String caminho) =>
      _enviar(() => _client.delete(_uri(caminho)), const {200, 204});

  static const _json = {'Content-Type': 'application/json'};

  Uri _uri(String caminho) => Uri.parse('$_baseUrl$caminho');

  Future<Object?> _enviar(
    Future<http.Response> Function() chamada,
    Set<int> aceitos,
  ) async {
    final http.Response resposta;
    try {
      resposta = await chamada().timeout(_timeout);
    } on SocketException {
      throw const ApiError(null);
    } on TimeoutException {
      throw const ApiError(null);
    } on http.ClientException {
      throw const ApiError(null);
    }

    final corpo = _decodificar(resposta);
    if (!aceitos.contains(resposta.statusCode)) {
      throw ApiError(resposta.statusCode, corpo);
    }
    return corpo;
  }

  static Object? _decodificar(http.Response resposta) {
    if (resposta.bodyBytes.isEmpty) return null;
    try {
      return jsonDecode(utf8.decode(resposta.bodyBytes));
    } on FormatException {
      return null;
    }
  }
}
