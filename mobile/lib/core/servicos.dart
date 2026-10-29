import 'package:flutter/widgets.dart';

import '../services/estoque.dart';
import '../services/pendencias.dart';
import 'api/cliente_api.dart';

/// Os serviços do app, ao alcance de qualquer tela por `Servicos.of(context)`.
/// Nos testes, troca-se o ClienteApi por um falso aqui, num lugar só.
class Servicos extends InheritedWidget {
  Servicos({
    super.key,
    required ClienteApi api,
    required this.solForte,
    required super.child,
  }) : estoque = EstoqueService(api),
       health = HealthService(api) {
    pendencias = PendenciasService(estoque);
  }

  final EstoqueService estoque;
  final HealthService health;
  late final PendenciasService pendencias;
  // O tema não escuta Servicos (é um InheritedWidget comum); quem o troca é
  // o ValueListenableBuilder em volta do MaterialApp, em app.dart.
  final ValueNotifier<bool> solForte;

  static Servicos of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<Servicos>()!;

  @override
  bool updateShouldNotify(Servicos oldWidget) =>
      estoque != oldWidget.estoque ||
      health != oldWidget.health ||
      pendencias != oldWidget.pendencias ||
      solForte != oldWidget.solForte;
}
