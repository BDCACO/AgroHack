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

  // O portão de login guarda o token aqui e lê quando a API diz que a sessão
  // não vale mais, pra voltar à tela de entrar.
  String? token;
  void Function()? aoPerderSessao;

  Future<Object?> get(String caminho, {Set<int> aceitos = const {200}}) =>
      _enviar(caminho, () => _client.get(_uri(caminho), headers: _cabecalhos()), aceitos);

  Future<Object?> post(
    String caminho, [
    Object corpo = const {},
    Set<int> aceitos = const {200, 201},
  ]) => _enviar(
    caminho,
    () => _client.post(_uri(caminho), headers: _cabecalhos(), body: jsonEncode(corpo)),
    aceitos,
  );

  Future<Object?> put(String caminho, Object corpo) => _enviar(
    caminho,
    () => _client.put(_uri(caminho), headers: _cabecalhos(), body: jsonEncode(corpo)),
    const {200},
  );

  Future<void> delete(String caminho) => _enviar(
    caminho,
    () => _client.delete(_uri(caminho), headers: _cabecalhos()),
    const {200, 204},
  );

  Map<String, String> _cabecalhos() => {
    'Content-Type': 'application/json',
    if (token != null) 'Authorization': 'Bearer $token',
  };

  Uri _uri(String caminho) => Uri.parse('$_baseUrl$caminho');

  Future<Object?> _enviar(
    String caminho,
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
      // Sessão perdida: não no próprio login, que já devolve a mensagem certa.
      if (resposta.statusCode == 401 && caminho != '/auth/entrar') {
        aoPerderSessao?.call();
      }
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
