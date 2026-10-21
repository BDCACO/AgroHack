import 'package:flutter/material.dart';

/// A importação de planilha ainda é só pelo site: no app falta escolher o
/// arquivo no celular (file_picker) e mostrar a prévia antes de gravar.
class ImportarPage extends StatelessWidget {
  const ImportarPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(32),
        child: Text(
          'Por enquanto, a importação de planilhas é feita pelo site.',
          textAlign: TextAlign.center,
        ),
      ),
    );
  }
}
