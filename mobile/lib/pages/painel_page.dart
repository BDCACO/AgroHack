import 'package:flutter/material.dart';

import '../core/servicos.dart';
import '../core/tema.dart';
import '../models/api.dart';
import '../widgets/carregar_dados.dart';

/// Os alertas de todos os insumos, os mais graves primeiro, com a justificativa.
class PainelPage extends StatelessWidget {
  const PainelPage({super.key});

  @override
  Widget build(BuildContext context) {
    final estoque = Servicos.of(context).estoque;
    return CarregarDados<List<Insumo>>(
      buscar: estoque.listarInsumos,
      construir: (context, insumos) {
        final alertas = [
          for (final insumo in insumos)
            for (final alerta in insumo.analise.alertas) (insumo, alerta),
        ]..sort((a, b) => a.$2.gravidade.index.compareTo(b.$2.gravidade.index));

        if (alertas.isEmpty) {
          return const EstadoVazio('Nenhum alerta. O estoque está em dia.');
        }
        return ListView.separated(
          padding: const EdgeInsets.all(16),
          itemCount: alertas.length,
          separatorBuilder: (_, _) => const SizedBox(height: 8),
          itemBuilder: (context, i) {
            final (insumo, alerta) = alertas[i];
            return Card(
              child: ListTile(
                leading: Icon(
                  Icons.circle,
                  size: 12,
                  color: alerta.gravidade.cor,
                ),
                title: Text('${alerta.tipo.rotulo} · ${insumo.nome}'),
                subtitle: Text(alerta.justificativa),
                trailing: Text(alerta.gravidade.texto),
              ),
            );
          },
        );
      },
    );
  }
}
