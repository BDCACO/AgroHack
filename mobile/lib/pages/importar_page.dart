import 'package:flutter/material.dart';

import '../core/tema.dart';

/// A importação de planilha ainda é só pelo site: no app falta escolher o
/// arquivo no celular (file_picker) e mostrar a prévia antes de gravar.
class ImportarPage extends StatelessWidget {
  const ImportarPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.upload_file_outlined,
              size: 56,
              color: Cores.campo600.withValues(alpha: 0.5),
            ),
            const SizedBox(height: 16),
            Text(
              'Por enquanto, a importação de planilhas é feita pelo site.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyLarge,
            ),
          ],
        ),
      ),
    );
  }
}
