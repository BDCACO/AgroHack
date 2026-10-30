import 'package:flutter/material.dart';

import 'app.dart';
import 'core/api/cliente_api.dart';
import 'services/auth.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final api = ClienteApi();
  // Carregado antes do primeiro frame: a 1ª busca de cada aba já sai com o
  // token, em vez de levar um 401 certo antes de tentar de novo.
  api.token = await AuthService(api).tokenSalvo();
  runApp(CampoCertoApp(api: api));
}
