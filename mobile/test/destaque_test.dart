import 'package:campocerto/widgets/destaque.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  Color corDe(WidgetTester tester) =>
      tester.widget<ColoredBox>(find.byKey(const ValueKey('destaque'))).color;

  testWidgets('ativo pinta o fundo e esmaece sozinho até sumir', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(home: Destaque(ativo: true, child: Text('linha'))),
    );

    expect(corDe(tester).a, greaterThan(0));

    await tester.pump(const Duration(milliseconds: 1600));
    expect(corDe(tester), Colors.transparent);
  });

  testWidgets('sem ativo nunca pinta nada', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(home: Destaque(ativo: false, child: Text('linha'))),
    );

    expect(corDe(tester), Colors.transparent);
  });
}
