import 'package:flutter/material.dart';

import '../core/servicos.dart';
import '../core/tema.dart';
import '../models/api.dart';
import '../widgets/carregar_dados.dart';
import '../widgets/formato.dart';

class InsumosPage extends StatelessWidget {
  const InsumosPage({super.key});

  @override
  Widget build(BuildContext context) {
    final estoque = Servicos.of(context).estoque;
    return CarregarDados<List<Insumo>>(
      buscar: estoque.listarInsumos,
      construir: (context, insumos) {
        if (insumos.isEmpty) {
          return const EstadoVazio('Nenhum insumo cadastrado ainda.');
        }
        return ListView.builder(
          itemCount: insumos.length,
          itemBuilder: (context, i) {
            final insumo = insumos[i];
            final maisGrave = insumo.analise.alertas
                .map((alerta) => alerta.gravidade)
                .fold<Gravidade?>(
                  null,
                  (pior, g) => pior == null || g.index < pior.index ? g : pior,
                );
            return ListTile(
              leading: Icon(
                Icons.circle,
                size: 12,
                color: maisGrave?.cor ?? Cores.campo600,
              ),
              title: Text(insumo.nome),
              subtitle: Text(
                maisGrave == null ? 'Sem alertas' : maisGrave.texto,
              ),
              trailing: Text(
                '${formatarQuantidade(insumo.estoqueAtual)} ${insumo.unidade}',
              ),
            );
          },
        );
      },
    );
  }
}
