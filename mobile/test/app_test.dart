import 'dart:convert';

import 'package:campocerto/app.dart';
import 'package:campocerto/core/api/cliente_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'dados.dart';

/// O app inteiro contra uma API falsa, que responde como a de verdade.
Widget _app({bool apiNoAr = true}) {
  final respostas = <String, Object>{
    '/v1/insumos': [insumoComAlerta, insumoSemAlerta],
    '/v1/movimentacoes': [movimentacao],
    '/v1/ready': {'status': 'pronto', 'database': 'ok'},
  };
  final client = MockClient((pedido) async {
    if (!apiNoAr) throw http.ClientException('sem rede');
    final corpo = respostas[pedido.url.path];
    return corpo == null
        ? http.Response('', 404)
        : http.Response.bytes(utf8.encode(jsonEncode(corpo)), 200);
  });
  return CampoCertoApp(
    api: ClienteApi(client: client, baseUrl: 'http://api/v1'),
  );
}

Future<void> _irPara(WidgetTester tester, String aba) async {
  await tester.tap(
    find.descendant(of: find.byType(NavigationBar), matching: find.text(aba)),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('o Painel abre com os alertas e a justificativa', (tester) async {
    await tester.pumpWidget(_app());
    await tester.pumpAndSettle();

    expect(find.text('Abaixo do mínimo · Ureia'), findsOneWidget);
    expect(
      find.text('Estoque de 120 kg, abaixo do mínimo de 200 kg.'),
      findsOneWidget,
    );
    expect(find.text('Urgente'), findsOneWidget);
  });

  testWidgets('Insumos mostra o estoque com separador de milhar', (
    tester,
  ) async {
    await tester.pumpWidget(_app());
    await tester.pumpAndSettle();
    await _irPara(tester, 'Insumos');

    expect(find.text('120 kg'), findsOneWidget);
    expect(find.text('1.500 t'), findsOneWidget);
    expect(find.text('Sem alertas'), findsOneWidget);
  });

  testWidgets('Movimentações mostra a saída com o nome do insumo', (
    tester,
  ) async {
    await tester.pumpWidget(_app());
    await tester.pumpAndSettle();
    await _irPara(tester, 'Movimentações');

    expect(find.text('Ureia'), findsOneWidget);
    expect(find.text('20/10/2026'), findsOneWidget);
    expect(find.text('−30 kg'), findsOneWidget);
  });

  testWidgets('Sistema mostra API e banco no ar', (tester) async {
    await tester.pumpWidget(_app());
    await tester.pumpAndSettle();
    await _irPara(tester, 'Sistema');

    expect(find.text('No ar'), findsOneWidget);
    expect(find.text('Conectado'), findsOneWidget);
  });

  testWidgets('sem API, avisa e oferece tentar de novo', (tester) async {
    await tester.pumpWidget(_app(apiNoAr: false));
    await tester.pumpAndSettle();

    expect(
      find.text('Sem resposta do servidor. Tente de novo em instantes.'),
      findsOneWidget,
    );
    expect(find.text('Tentar de novo'), findsOneWidget);
  });
}
