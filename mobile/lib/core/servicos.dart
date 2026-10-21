import 'package:flutter/widgets.dart';

import '../services/estoque.dart';
import 'api/cliente_api.dart';

/// Os serviços do app, ao alcance de qualquer tela por `Servicos.of(context)`.
/// Nos testes, troca-se o ClienteApi por um falso aqui, num lugar só.
class Servicos extends InheritedWidget {
  Servicos({super.key, required ClienteApi api, required super.child})
    : estoque = EstoqueService(api),
      health = HealthService(api);

  final EstoqueService estoque;
  final HealthService health;

  static Servicos of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<Servicos>()!;

  @override
  bool updateShouldNotify(Servicos oldWidget) =>
      estoque != oldWidget.estoque || health != oldWidget.health;
}
