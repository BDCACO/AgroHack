import 'package:flutter/widgets.dart';

import '../models/api.dart';
import '../services/auth.dart';
import '../services/estoque.dart';
import '../services/pendencias.dart';
import 'api/cliente_api.dart';

/// Os serviços do app, ao alcance de qualquer tela por `Servicos.of(context)`.
/// Nos testes, troca-se o ClienteApi por um falso aqui, num lugar só.
class Servicos extends InheritedWidget {
  Servicos({
    super.key,
    required this.api,
    required this.solForte,
    required this.usuario,
    required super.child,
  }) : estoque = EstoqueService(api),
       health = HealthService(api),
       auth = AuthService(api) {
    pendencias = PendenciasService(estoque);
  }

  // Exposto só para o "Sair" limpar o token que o próprio login guardou nele.
  final ClienteApi api;
  final EstoqueService estoque;
  final HealthService health;
  final AuthService auth;
  late final PendenciasService pendencias;
  // Nem o tema nem quem fez login escutam Servicos (é um InheritedWidget
  // comum); quem os troca são os ValueListenableBuilder em volta do
  // MaterialApp, em app.dart.
  final ValueNotifier<bool> solForte;
  final ValueNotifier<Usuario?> usuario;

  static Servicos of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<Servicos>()!;

  @override
  bool updateShouldNotify(Servicos oldWidget) =>
      api != oldWidget.api ||
      estoque != oldWidget.estoque ||
      health != oldWidget.health ||
      auth != oldWidget.auth ||
      pendencias != oldWidget.pendencias ||
      solForte != oldWidget.solForte ||
      usuario != oldWidget.usuario;
}
