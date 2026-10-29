import 'package:flutter/material.dart';

import '../core/servicos.dart';
import '../core/tema.dart';
import '../models/api.dart';
import '../services/pendencias.dart';
import '../widgets/carregar_dados.dart';
import '../widgets/formato.dart';
import 'lancar_movimentacao_page.dart';

class MovimentacoesPage extends StatefulWidget {
  const MovimentacoesPage({super.key});

  @override
  State<MovimentacoesPage> createState() => _MovimentacoesPageState();
}

class _MovimentacoesPageState extends State<MovimentacoesPage> {
  // Muda a cada lançamento ou ação numa pendência, só para forçar o
  // CarregarDados a buscar de novo.
  var _versao = 0;

  Future<void> _lancar() async {
    final resultado = await Navigator.push<String>(
      context,
      MaterialPageRoute(builder: (_) => const LancarMovimentacaoPage()),
    );
    if (resultado == null || !mounted) return;
    setState(() => _versao++);
    if (resultado == 'offline') {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Sem internet: o lançamento foi guardado e será enviado '
            'quando a rede voltar.',
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final servicos = Servicos.of(context);
    return Scaffold(
      body: CarregarDados<(List<Movimentacao>, Map<int, Insumo>, List<Pendencia>)>(
        key: ValueKey(_versao),
        buscar: () async {
          // Tenta mandar o que estiver pendente antes de montar a lista.
          await servicos.pendencias.tentarEnviar();
          final (movimentacoes, insumosLista) = await (
            servicos.estoque.listarMovimentacoes(),
            servicos.estoque.listarInsumos(),
          ).wait;
          final pendentes = await servicos.pendencias.listar();
          return (
            movimentacoes,
            {for (final i in insumosLista) i.id: i},
            pendentes,
          );
        },
        construir: (context, dados) {
          final (movimentacoes, insumos, pendentes) = dados;
          if (movimentacoes.isEmpty && pendentes.isEmpty) {
            return const EstadoVazio('Nenhuma movimentação lançada ainda.');
          }
          return ListView.builder(
            itemCount: pendentes.length + movimentacoes.length,
            itemBuilder: (context, i) {
              if (i < pendentes.length) {
                final pendencia = pendentes[i];
                final insumo = insumos[pendencia.dados.insumoId];
                return _ItemPendente(
                  pendencia: pendencia,
                  nomeDoInsumo:
                      insumo?.nome ?? 'Insumo ${pendencia.dados.insumoId}',
                  onTentar: () async {
                    await servicos.pendencias.tentarEnviar(
                      apenas: pendencia.criadoEm,
                    );
                    if (mounted) setState(() => _versao++);
                  },
                  onDescartar: () async {
                    await servicos.pendencias.descartar(pendencia.criadoEm);
                    if (mounted) setState(() => _versao++);
                  },
                );
              }
              final mov = movimentacoes[i - pendentes.length];
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

/// Um lançamento ainda sem confirmação da API: sem rede, ou recusado (com o
/// motivo). "Tentar de novo" manda só esse; "Descartar" apaga de vez.
class _ItemPendente extends StatelessWidget {
  const _ItemPendente({
    required this.pendencia,
    required this.nomeDoInsumo,
    required this.onTentar,
    required this.onDescartar,
  });

  final Pendencia pendencia;
  final String nomeDoInsumo;
  final VoidCallback onTentar;
  final VoidCallback onDescartar;

  @override
  Widget build(BuildContext context) {
    final entrada = pendencia.dados.tipo == TipoMovimentacao.entrada;
    return ListTile(
      leading: Icon(
        entrada ? Icons.south_west : Icons.north_east,
        color: Cores.terra700,
      ),
      title: Text(nomeDoInsumo),
      subtitle: Text(
        pendencia.erro ?? 'Sem internet. Será enviado quando a rede voltar.',
      ),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Tentar de novo',
            onPressed: onTentar,
          ),
          IconButton(
            icon: const Icon(Icons.delete_outline),
            tooltip: 'Descartar',
            onPressed: onDescartar,
          ),
        ],
      ),
    );
  }
}
