import 'package:shared_preferences/shared_preferences.dart';

import '../core/api/cliente_api.dart';
import '../models/api.dart';

const _chaveToken = 'auth.token';

/// Sessão: entrar, sair e o token guardado no aparelho. Mesmas rotas do
/// frontend/src/services/sessao.ts e frontend/src/services/token.ts.
class AuthService {
  const AuthService(this._api);

  final ClienteApi _api;

  Future<Entrada> entrar(String login, String senha) async => Entrada.fromJson(
    await _api.post('/auth/entrar', {
      'login': login,
      'senha': senha,
      'dispositivo': 'App',
    })
    as Json,
  );

  Future<Usuario> quemSouEu() async =>
      Usuario.fromJson(await _api.get('/auth/eu') as Json);

  /// Revoga a sessão no servidor; quem chama limpa o token local depois,
  /// com sucesso ou não (sem internet, por exemplo).
  Future<void> sair() => _api.post('/auth/sair', const {}, const {200, 204});

  Future<String?> tokenSalvo() async =>
      (await SharedPreferences.getInstance()).getString(_chaveToken);

  Future<void> salvarToken(String token) async =>
      (await SharedPreferences.getInstance()).setString(_chaveToken, token);

  Future<void> limparToken() async =>
      (await SharedPreferences.getInstance()).remove(_chaveToken);
}
