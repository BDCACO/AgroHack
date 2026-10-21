import 'package:flutter/material.dart';

import '../core/servicos.dart';
import '../core/tema.dart';
import '../models/api.dart';
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
          itemCount: movimentacoes.length,
          itemBuilder: (context, i) {
            final mov = movimentacoes[i];
            final insumo = insumos[mov.insumoId];
            final entrada = mov.tipo == TipoMovimentacao.entrada;
            return ListTile(
              leading: Icon(
                entrada ? Icons.south_west : Icons.north_east,
                color: entrada ? Cores.campo600 : Cores.terra700,
              ),
              title: Text(insumo?.nome ?? 'Insumo ${mov.insumoId}'),
              subtitle: Text(formatarData(mov.data)),
              trailing: Text(
                '${entrada ? '+' : '−'}${formatarQuantidade(mov.quantidade)} '
                '${insumo?.unidade ?? ''}',
              ),
            );
          },
        );
      },
    );
  }
}
