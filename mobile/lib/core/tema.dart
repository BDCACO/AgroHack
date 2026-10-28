import 'package:flutter/material.dart';

import '../models/api.dart';

/// Cores da marca, as mesmas do frontend/src/styles/main.css.
abstract final class Cores {
  /// Verde de lavoura: a cor da marca.
  static const campo50 = Color(0xFFF2F8EF);
  static const campo600 = Color(0xFF3F7A2C);
  static const campo800 = Color(0xFF29501E);

  /// Terra e palha: o acento quente.
  static const terra100 = Color(0xFFF3ECE2);
  static const terra700 = Color(0xFF7A5A32);
}

ThemeData temaDoApp() {
  final esquema = ColorScheme.fromSeed(
    seedColor: Cores.campo600,
    primary: Cores.campo600,
    secondary: Cores.terra700,
  );
  return ThemeData(
    colorScheme: esquema,
    scaffoldBackgroundColor: Cores.campo50,
    appBarTheme: const AppBarTheme(
      backgroundColor: Cores.campo50,
      foregroundColor: Cores.campo800,
    ),
    // Cartão branco com sombra de verdade: no fundo verde-claro da tela, o
    // tom de superfície padrão do Material 3 quase não aparece.
    cardTheme: CardThemeData(
      color: Colors.white,
      elevation: 2,
      shadowColor: Cores.campo800.withValues(alpha: 0.18),
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
    ),
  );
}

/// Texto e cor de cada gravidade, como o SeloDeGravidade.vue do site.
extension AparenciaDaGravidade on Gravidade {
  String get texto => switch (this) {
    Gravidade.alta => 'Urgente',
    Gravidade.media => 'Atenção',
    Gravidade.baixa => 'Observar',
  };

  /// Pra ícone, bolinha e barra de progresso — não precisa do contraste de texto.
  Color get cor => switch (this) {
    Gravidade.alta => const Color(0xFFDC2626),
    Gravidade.media => const Color(0xFFF59E0B),
    Gravidade.baixa => const Color(0xFF0EA5E9),
  };

  /// Pra texto em fundo claro: a mesma cor, mas escura o bastante pra passar
  /// de 4,5:1 de contraste (o âmbar e o azul claros de `cor` não passavam).
  Color get corTexto => switch (this) {
    Gravidade.alta => const Color(0xFFB91C1C),
    Gravidade.media => const Color(0xFFB45309),
    Gravidade.baixa => const Color(0xFF0369A1),
  };
}

/// Os mesmos rótulos do CartaoDeAlerta.vue do site.
extension RotuloDoAlerta on TipoAlerta {
  String get rotulo => switch (this) {
    TipoAlerta.abaixoDoMinimo => 'Abaixo do mínimo',
    TipoAlerta.riscoDeFalta => 'Risco de falta',
    TipoAlerta.vencido => 'Lote vencido',
    TipoAlerta.vencimentoProximo => 'Vencimento próximo',
    TipoAlerta.excesso => 'Excesso de estoque',
    TipoAlerta.baixaMovimentacao => 'Baixa movimentação',
    TipoAlerta.consumoIncomum => 'Consumo incomum',
  };
}
