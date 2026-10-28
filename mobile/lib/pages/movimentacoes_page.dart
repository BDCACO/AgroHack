import 'package:flutter/material.dart';

import '../core/servicos.dart';
import '../core/tema.dart';
import '../models/api.dart';
import '../widgets/carregar_dados.dart';
import '../widgets/formato.dart';
import 'lancar_movimentacao_page.dart';

class MovimentacoesPage extends StatefulWidget {
  const MovimentacoesPage({super.key});

  @override
  State<MovimentacoesPage> createState() => _MovimentacoesPageState();
}

class _MovimentacoesPageState extends State<MovimentacoesPage> {
  // Muda a cada lançamento, só para forçar o CarregarDados a buscar de novo.
  var _versao = 0;

  Future<void> _lancar() async {
    final lancado = await Navigator.push<bool>(
      context,
      MaterialPageRoute(builder: (_) => const LancarMovimentacaoPage()),
    );
    if (lancado == true && mounted) setState(() => _versao++);
  }

  @override
  Widget build(BuildContext context) {
    final estoque = Servicos.of(context).estoque;
    return Scaffold(
      body: CarregarDados<(List<Movimentacao>, Map<int, Insumo>)>(
        key: ValueKey(_versao),
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
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _lancar,
        icon: const Icon(Icons.add),
        label: const Text('Lançar'),
      ),
    );
  }
}
