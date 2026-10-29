import 'dart:convert';

import 'package:campocerto/app.dart';
import 'package:campocerto/core/api/cliente_api.dart';
import 'package:campocerto/models/api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

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
  // A fila de pendências usa SharedPreferences; sem isso, dá
  // MissingPluginException nos testes de widget.
  setUp(() => SharedPreferences.setMockInitialValues({}));

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

  testWidgets('atualizar com a API fora mantém os dados e avisa', (
    tester,
  ) async {
    // O Painel também busca /v1/insumos ao abrir o app: a 1ª chamada é dele,
    // a 2ª é o primeiro carregamento da aba Insumos, só a 3ª (atualizar) falha.
    var chamadas = 0;
    final client = MockClient((pedido) async {
      if (pedido.url.path != '/v1/insumos') return http.Response('', 404);
      chamadas++;
      if (chamadas > 2) throw http.ClientException('sem rede');
      return http.Response.bytes(
        utf8.encode(jsonEncode([insumoComAlerta, insumoSemAlerta])),
        200,
      );
    });
    await tester.pumpWidget(
      CampoCertoApp(
        api: ClienteApi(client: client, baseUrl: 'http://api/v1'),
      ),
    );
    await tester.pumpAndSettle();
    await _irPara(tester, 'Insumos');

    final indicador = tester.widget<RefreshIndicator>(
      find.byType(RefreshIndicator),
    );
    await indicador.onRefresh();
    await tester.pumpAndSettle();

    expect(find.text('Ureia'), findsOneWidget);
    expect(
      find.text('Sem resposta do servidor. Tente de novo em instantes.'),
      findsOneWidget,
    );
  });

  testWidgets('lançar uma movimentação nova aparece na lista ao voltar', (
    tester,
  ) async {
    final novaMovimentacao = <String, dynamic>{
      'id': 11,
      'insumo_id': 2,
      'tipo': 'entrada',
      'data': '2026-10-27',
      'quantidade': 500,
      'validade': null,
    };
    // A 1ª busca de /v1/movimentacoes é o load inicial da aba; a 2ª é ao
    // voltar do formulário, já com o lançamento novo.
    var buscasDeMovimentacoes = 0;
    final client = MockClient((pedido) async {
      if (pedido.url.path == '/v1/insumos') {
        return http.Response.bytes(
          utf8.encode(jsonEncode([insumoComAlerta, insumoSemAlerta])),
          200,
        );
      }
      if (pedido.url.path == '/v1/movimentacoes') {
        if (pedido.method == 'POST') {
          return http.Response.bytes(
            utf8.encode(jsonEncode(novaMovimentacao)),
            201,
          );
        }
        buscasDeMovimentacoes++;
        final lista = buscasDeMovimentacoes == 1
            ? [movimentacao]
            : [movimentacao, novaMovimentacao];
        return http.Response.bytes(utf8.encode(jsonEncode(lista)), 200);
      }
      return http.Response('', 404);
    });
    await tester.pumpWidget(
      CampoCertoApp(
        api: ClienteApi(client: client, baseUrl: 'http://api/v1'),
      ),
    );
    await tester.pumpAndSettle();
    await _irPara(tester, 'Movimentações');

    await tester.tap(find.byType(FloatingActionButton));
    await tester.pumpAndSettle();

    await tester.tap(find.byType(DropdownButtonFormField<Insumo>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Calcário'));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextFormField), '500');
    await tester.tap(find.widgetWithText(FilledButton, 'Lançar'));
    await tester.pumpAndSettle();

    expect(find.text('Ureia'), findsOneWidget);
    expect(find.text('Calcário'), findsOneWidget);
    expect(find.text('+500 t'), findsOneWidget);
  });

  testWidgets('lançar sem rede guarda como pendência e envia quando volta', (
    tester,
  ) async {
    final novaMovimentacao = <String, dynamic>{
      'id': 12,
      'insumo_id': 2,
      'tipo': 'entrada',
      'data': '2026-10-27',
      'quantidade': 300,
      'validade': null,
    };
    var apiNoAr = false;
    var enviouComSucesso = false;
    final client = MockClient((pedido) async {
      if (pedido.url.path == '/v1/insumos') {
        return http.Response.bytes(
          utf8.encode(jsonEncode([insumoComAlerta, insumoSemAlerta])),
          200,
        );
      }
      if (pedido.url.path == '/v1/movimentacoes') {
        if (pedido.method == 'POST') {
          if (!apiNoAr) throw http.ClientException('sem rede');
          enviouComSucesso = true;
          return http.Response.bytes(
            utf8.encode(jsonEncode(novaMovimentacao)),
            201,
          );
        }
        final lista = enviouComSucesso
            ? [movimentacao, novaMovimentacao]
            : [movimentacao];
        return http.Response.bytes(utf8.encode(jsonEncode(lista)), 200);
      }
      return http.Response('', 404);
    });
    await tester.pumpWidget(
      CampoCertoApp(
        api: ClienteApi(client: client, baseUrl: 'http://api/v1'),
      ),
    );
    await tester.pumpAndSettle();
    await _irPara(tester, 'Movimentações');

    await tester.tap(find.byType(FloatingActionButton));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(DropdownButtonFormField<Insumo>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Calcário'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField), '300');
    await tester.tap(find.widgetWithText(FilledButton, 'Lançar'));
    await tester.pumpAndSettle();

    expect(
      find.text(
        'Sem internet: o lançamento foi guardado e será enviado '
        'quando a rede voltar.',
      ),
      findsOneWidget,
    );
    expect(
      find.text('Sem internet. Será enviado quando a rede voltar.'),
      findsOneWidget,
    );
    expect(find.text('Calcário'), findsOneWidget);

    apiNoAr = true;
    await tester.tap(find.byTooltip('Tentar de novo'));
    await tester.pumpAndSettle();

    expect(
      find.text('Sem internet. Será enviado quando a rede voltar.'),
      findsNothing,
    );
    expect(find.text('+300 t'), findsOneWidget);
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
