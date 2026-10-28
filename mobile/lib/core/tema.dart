import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show SystemUiOverlayStyle;

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
    // Cabeçalho com cor sólida da marca, não só texto escuro num fundo claro.
    appBarTheme: const AppBarTheme(
      backgroundColor: Cores.campo600,
      foregroundColor: Colors.white,
      elevation: 0,
      centerTitle: false,
      systemOverlayStyle: SystemUiOverlayStyle.light,
      titleTextStyle: TextStyle(
        color: Colors.white,
        fontSize: 22,
        fontWeight: FontWeight.w700,
      ),
    ),
    // Barra de baixo no mesmo verde do cabeçalho: as duas pontas da tela
    // ficam marcadas, o conteúdo claro no meio.
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: Cores.campo600,
      indicatorColor: Colors.white.withValues(alpha: 0.22),
      iconTheme: WidgetStateProperty.resolveWith(
        (estados) => IconThemeData(
          color: estados.contains(WidgetState.selected)
              ? Colors.white
              : Colors.white70,
        ),
      ),
      labelTextStyle: WidgetStateProperty.resolveWith(
        (estados) => TextStyle(
          fontSize: 12,
          color: estados.contains(WidgetState.selected)
              ? Colors.white
              : Colors.white70,
          fontWeight: estados.contains(WidgetState.selected)
              ? FontWeight.w700
              : FontWeight.w500,
        ),
      ),
    ),
    // Cartão branco com sombra de verdade: no fundo verde-claro da tela, o
    // tom de superfície padrão do Material 3 quase não aparece.
    cardTheme: CardThemeData(
      color: Colors.white,
      elevation: 2,
      shadowColor: Cores.campo800.withValues(alpha: 0.18),
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
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

  // Paleta "terra": vermelho-barro, ocre de colheita e verde-sálvia — a mesma
  // família de cor da marca, em vez do vermelho/âmbar/azul genérico de
  // dashboard que destoava do resto do app.

  /// Pra ícone, bolinha e barra de progresso — não precisa do contraste de texto.
  Color get cor => switch (this) {
    Gravidade.alta => const Color(0xFFC1443B),
    Gravidade.media => const Color(0xFFB9770E),
    Gravidade.baixa => const Color(0xFF5B8C78),
  };

  /// Pra texto em fundo claro (ou fundo sólido com texto branco): a mesma
  /// cor, mas escura o bastante pra passar de 4,5:1 de contraste.
  Color get corTexto => switch (this) {
    Gravidade.alta => const Color(0xFF8F2F28),
    Gravidade.media => const Color(0xFF7A5107),
    Gravidade.baixa => const Color(0xFF3F6354),
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
