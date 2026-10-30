import 'dart:convert';

import 'package:campocerto/app.dart';
import 'package:campocerto/core/api/cliente_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'dados.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets(
    'API com login ligado pede entrar, e logar leva pro Painel',
    (tester) async {
      const token = 'token-de-teste';
      final client = MockClient((pedido) async {
        if (pedido.url.path == '/v1/auth/entrar') {
          final corpo = jsonDecode(pedido.body) as Map;
          if (corpo['login'] == 'dono' && corpo['senha'] == '123456') {
            return http.Response.bytes(
              utf8.encode(
                jsonEncode({
                  'token': token,
                  'expira_em': '2027-01-01T00:00:00Z',
                  'usuario': {
                    'id': 1,
                    'nome': 'Dona da Fazenda',
                    'login': 'dono',
                    'papel': 'dono',
                  },
                }),
              ),
              200,
            );
          }
          return http.Response.bytes(
            utf8.encode(jsonEncode({'detail': 'Login ou senha incorretos.'})),
            401,
          );
        }
        if (pedido.headers['Authorization'] != 'Bearer $token') {
          return http.Response.bytes(
            utf8.encode(
              jsonEncode({'detail': 'Entre com o seu login e senha para continuar.'}),
            ),
            401,
          );
        }
        if (pedido.url.path == '/v1/insumos') {
          return http.Response.bytes(
            utf8.encode(jsonEncode([insumoSemAlerta])),
            200,
          );
        }
        return http.Response('', 404);
      });

      await tester.pumpWidget(
        CampoCertoApp(api: ClienteApi(client: client, baseUrl: 'http://api/v1')),
      );
      await tester.pumpAndSettle();

      expect(find.text('Entre para continuar'), findsOneWidget);

      await tester.enterText(find.widgetWithText(TextFormField, 'Login'), 'dono');
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Senha'),
        '123456',
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Entrar'));
      await tester.pumpAndSettle();

      // Chegou no Painel autenticado: sem alertas, ele mostra "Tudo em dia".
      expect(find.text('Tudo em dia'), findsOneWidget);
    },
  );

  testWidgets('senha errada mostra o erro e não sai da tela de entrar', (
    tester,
  ) async {
    final client = MockClient((pedido) async {
      if (pedido.url.path == '/v1/auth/entrar') {
        return http.Response.bytes(
          utf8.encode(
            jsonEncode({
              'detail':
                  'Login ou senha incorretos. Depois de 5 tentativas erradas '
                  'seguidas, o login fica bloqueado por 15 minutos.',
            }),
          ),
          401,
        );
      }
      // Sem token nenhum, a API de verdade também recusaria com 401: é isso
      // que faz o app mostrar a tela de entrar antes mesmo de tentar logar.
      return http.Response.bytes(
        utf8.encode(
          jsonEncode({'detail': 'Entre com o seu login e senha para continuar.'}),
        ),
        401,
      );
    });

    await tester.pumpWidget(
      CampoCertoApp(api: ClienteApi(client: client, baseUrl: 'http://api/v1')),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.widgetWithText(TextFormField, 'Login'), 'dono');
    await tester.enterText(find.widgetWithText(TextFormField, 'Senha'), 'errada');
    await tester.tap(find.widgetWithText(FilledButton, 'Entrar'));
    await tester.pumpAndSettle();

    expect(
      find.text(
        'Login ou senha incorretos. Depois de 5 tentativas erradas '
        'seguidas, o login fica bloqueado por 15 minutos.',
      ),
      findsOneWidget,
    );
    expect(find.text('Entre para continuar'), findsOneWidget);
  });
}
