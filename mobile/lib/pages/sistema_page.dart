import 'package:flutter/material.dart';

import '../core/config.dart';
import '../core/servicos.dart';
import '../models/api.dart';
import '../widgets/carregar_dados.dart';

/// A situação da API e do banco: a verificação de que o app chega até eles.
class SistemaPage extends StatelessWidget {
  const SistemaPage({super.key});

  @override
  Widget build(BuildContext context) {
    final health = Servicos.of(context).health;
    return CarregarDados<ReadinessResponse>(
      buscar: health.buscarReadiness,
      construir: (context, prontidao) => ListView(
        padding: const EdgeInsets.symmetric(vertical: 8),
        children: [
          ListTile(
            leading: const Icon(Icons.cloud_done_outlined),
            title: const Text('API'),
            subtitle: Text(prontidao.pronto ? 'No ar' : 'Indisponível'),
          ),
          ListTile(
            leading: Icon(
              prontidao.bancoOk ? Icons.storage : Icons.error_outline,
            ),
            title: const Text('Banco de dados'),
            subtitle: Text(prontidao.bancoOk ? 'Conectado' : 'Com erro'),
          ),
          const ListTile(
            leading: Icon(Icons.link),
            title: Text('Endereço da API'),
            subtitle: Text(urlDaApi),
          ),
        ],
      ),
    );
  }
}
