import 'dart:convert';

import 'package:campocerto/core/api/cliente_api.dart';
import 'package:campocerto/models/api.dart';
import 'package:campocerto/services/estoque.dart';
import 'package:campocerto/widgets/formato.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'dados.dart';

ClienteApi _api(MockClientHandler handler) =>
    ClienteApi(client: MockClient(handler), baseUrl: 'http://api/v1');

void main() {
  group('modelos', () {
    test('lê o insumo com a análise como a API manda', () {
      final insumo = Insumo.fromJson(insumoComAlerta);

      expect(insumo.nome, 'Ureia');
      expect(insumo.estoqueAtual, 120.0); // inteiro no JSON vira double
      expect(insumo.analise.alertas.single.tipo, TipoAlerta.abaixoDoMinimo);
      expect(insumo.analise.alertas.single.gravidade, Gravidade.alta);
      expect(insumo.analise.reposicao!.pedirEm, DateTime(2026, 10, 25));
      expect(insumo.analise.limitacoes, ['Poucas saídas registradas.']);
    });

    test('manda a movimentação com datas em AAAA-MM-DD', () {
      final entrada = MovimentacaoEntrada(
        insumoId: 1,
        tipo: TipoMovimentacao.entrada,
        data: DateTime(2026, 3, 5),
        quantidade: 10,
        validade: DateTime(2027, 1, 9),
      );

      expect(entrada.toJson(), {
        'insumo_id': 1,
        'tipo': 'entrada',
        'data': '2026-03-05',
        'quantidade': 10.0,
        'validade': '2027-01-09',
      });
    });
  });

  group('ClienteApi', () {
    test('usa a frase da API no erro', () async {
      final api = _api(
        (_) async => http.Response.bytes(
          utf8.encode(
            jsonEncode({'detail': 'Já existe um insumo com esse nome.'}),
          ),
          409,
        ),
      );

      await expectLater(
        EstoqueService(api)
            .criarInsumo(const InsumoCadastro(nome: 'Ureia', unidade: 'kg')),
        throwsA(
          isA<ApiError>()
              .having((e) => e.status, 'status', 409)
              .having(
                (e) => e.mensagem,
                'mensagem',
                'Já existe um insumo com esse nome.',
              ),
        ),
      );
    });

    test('sem resposta vira ApiError sem status', () async {
      final api = _api((_) async => throw http.ClientException('sem rede'));

      await expectLater(
        EstoqueService(api).listarInsumos(),
        throwsA(isA<ApiError>().having((e) => e.status, 'status', isNull)),
      );
    });

    test('503 do /ready é resposta, não erro', () async {
      final api = _api(
        (_) async => http.Response(
          jsonEncode({'status': 'indisponivel', 'database': 'erro'}),
          503,
        ),
      );

      final prontidao = await HealthService(api).buscarReadiness();

      expect(prontidao.pronto, isFalse);
      expect(prontidao.bancoOk, isFalse);
    });

    test('lê acentos em UTF-8 mesmo sem charset no cabeçalho', () async {
      final api = _api(
        (_) async => http.Response.bytes(
          utf8.encode(jsonEncode([insumoComAlerta])),
          200,
        ),
      );

      final insumos = await EstoqueService(api).listarInsumos();

      expect(
        insumos.single.analise.alertas.single.justificativa,
        contains('mínimo'),
      );
    });
  });

  test('formata quantidade e data no jeito brasileiro', () {
    expect(formatarQuantidade(1500), '1.500');
    expect(formatarQuantidade(2.5), '2,5');
    expect(formatarQuantidade(1234567.125), '1.234.567,125');
    expect(formatarData(DateTime(2026, 3, 5)), '05/03/2026');
  });
}
