import 'package:campocerto/models/api.dart';
import 'package:campocerto/services/codigo_de_barras.dart';
import 'package:flutter_test/flutter_test.dart';

import 'dados.dart';

void main() {
  test('acha o insumo cujo código de barras bate', () {
    final ureia = Insumo.fromJson({
      ...insumoComAlerta,
      'codigo_de_barras': '7891234567890',
    });
    final calcario = Insumo.fromJson(insumoSemAlerta);

    final encontrado = insumoPeloCodigoDeBarras([
      ureia,
      calcario,
    ], '7891234567890');

    expect(encontrado, same(ureia));
  });

  test('não acha quando nenhum insumo tem esse código', () {
    final calcario = Insumo.fromJson(insumoSemAlerta);

    final encontrado = insumoPeloCodigoDeBarras([calcario], '7891234567890');

    expect(encontrado, isNull);
  });
}
