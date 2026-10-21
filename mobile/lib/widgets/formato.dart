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
