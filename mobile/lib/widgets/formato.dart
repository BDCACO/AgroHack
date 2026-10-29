import 'package:flutter/material.dart';

/// Um ícone que combina com a unidade, pra identificar o tipo de insumo
/// batendo o olho, sem precisar ler o nome inteiro.
IconData iconeDaUnidade(String unidade) => switch (unidade.toLowerCase()) {
  'l' => Icons.water_drop_outlined,
  'kg' || 't' => Icons.scale_outlined,
  'sc' => Icons.shopping_bag_outlined,
  'un' => Icons.inventory_2_outlined,
  _ => Icons.grain_outlined,
};

/// Quantidade no jeito brasileiro: 1.500 e 2,5 (sem zeros sobrando).
String formatarQuantidade(double valor) {
  final partes = valor.toStringAsFixed(3).split('.');
  final inteiro = partes[0].replaceAllMapped(
    RegExp(r'\B(?=(\d{3})+(?!\d))'),
    (_) => '.',
  );
  final decimais = partes[1].replaceFirst(RegExp(r'0+$'), '');
  return decimais.isEmpty ? inteiro : '$inteiro,$decimais';
}

/// Data no formato DD/MM/AAAA.
String formatarData(DateTime data) =>
    '${data.day.toString().padLeft(2, '0')}/'
    '${data.month.toString().padLeft(2, '0')}/${data.year}';

/// "Hoje", "Ontem" ou a data, pra separar os grupos de uma lista por dia.
String formatarDiaRelativo(DateTime data) {
  final hoje = DateTime.now();
  final diferenca = DateTime(
    hoje.year,
    hoje.month,
    hoje.day,
  ).difference(DateTime(data.year, data.month, data.day)).inDays;
  return switch (diferenca) {
    0 => 'Hoje',
    1 => 'Ontem',
    _ => formatarData(data),
  };
}
