import 'package:flutter/material.dart';

import '../core/servicos.dart';
import '../core/tema.dart';
import '../models/api.dart';
import '../widgets/aparece_em_cascata.dart';
import '../widgets/carregar_dados.dart';
import '../widgets/formato.dart';

class MovimentacoesPage extends StatelessWidget {
  const MovimentacoesPage({super.key});

  @override
  Widget build(BuildContext context) {
    final estoque = Servicos.of(context).estoque;
    return CarregarDados<(List<Movimentacao>, Map<int, Insumo>)>(
      buscar: () async {
        final (movimentacoes, insumos) = await (
          estoque.listarMovimentacoes(),
          estoque.listarInsumos(),
        ).wait;
        return (movimentacoes, {for (final i in insumos) i.id: i});
      },
      construir: (context, dados) {
        final (movimentacoes, insumos) = dados;
        if (movimentacoes.isEmpty) {
          return const EstadoVazio('Nenhuma movimentação lançada ainda.');
        }
        return ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: movimentacoes.length,
          itemBuilder: (context, i) {
            final mov = movimentacoes[i];
            final insumo = insumos[mov.insumoId];
            final entrada = mov.tipo == TipoMovimentacao.entrada;
            final cor = entrada ? Cores.campo600 : Cores.terra700;
            return ApareceEmCascata(
              indice: i,
              child: Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Card(
                  child: ListTile(
                    leading: CircleAvatar(
                      backgroundColor: cor.withValues(alpha: 0.12),
                      foregroundColor: cor,
                      child: Icon(entrada ? Icons.south_west : Icons.north_east),
                    ),
                    title: Text(
                      insumo?.nome ?? 'Insumo ${mov.insumoId}',
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                    subtitle: Text(formatarData(mov.data)),
                    trailing: Text(
                      '${entrada ? '+' : '−'}${formatarQuantidade(mov.quantidade)} '
                      '${insumo?.unidade ?? ''}',
                      style: TextStyle(color: cor, fontWeight: FontWeight.w700),
                    ),
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }
}
