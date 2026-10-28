import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../core/servicos.dart';
import '../core/tema.dart';
import '../models/api.dart';
import '../widgets/aparece_em_cascata.dart';
import '../widgets/carregar_dados.dart';
import '../widgets/formato.dart';

class MovimentacoesPage extends StatefulWidget {
  const MovimentacoesPage({super.key});

  @override
  State<MovimentacoesPage> createState() => _MovimentacoesPageState();
}

class _MovimentacoesPageState extends State<MovimentacoesPage> {
  TipoMovimentacao? _filtro;

  Map<DateTime, List<Movimentacao>> _agruparPorDia(List<Movimentacao> lista) {
    final grupos = <DateTime, List<Movimentacao>>{};
    for (final mov in lista) {
      final dia = DateTime(mov.data.year, mov.data.month, mov.data.day);
      (grupos[dia] ??= []).add(mov);
    }
    return grupos;
  }

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

        final filtradas = _filtro == null
            ? movimentacoes
            : movimentacoes.where((m) => m.tipo == _filtro).toList();
        final grupos = _agruparPorDia(filtradas);

        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _ResumoDeMovimentacoes(movimentacoes: movimentacoes),
            const SizedBox(height: 16),
            _FiltroDeTipo(
              selecionado: _filtro,
              aoMudar: (tipo) => setState(() => _filtro = tipo),
            ),
            const SizedBox(height: 8),
            if (filtradas.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 32),
                child: Center(child: Text('Nada lançado com esse filtro.')),
              )
            else
              for (final grupo in grupos.entries) ...[
                Padding(
                  padding: const EdgeInsets.fromLTRB(4, 12, 4, 8),
                  child: Text(
                    formatarDiaRelativo(grupo.key),
                    style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13),
                  ),
                ),
                for (final (i, mov) in grupo.value.indexed)
                  ApareceEmCascata(
                    indice: i,
                    child: Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: _CartaoDeMovimentacao(
                        mov: mov,
                        insumo: insumos[mov.insumoId],
                      ),
                    ),
                  ),
              ],
          ],
        );
      },
    );
  }
}

/// Entradas/saídas no total e, se tiver dado o bastante, um gráfico de barras
/// por dia — com menos de 4 dias um gráfico só atrapalha, melhor nem mostrar.
class _ResumoDeMovimentacoes extends StatelessWidget {
  const _ResumoDeMovimentacoes({required this.movimentacoes});

  final List<Movimentacao> movimentacoes;

  @override
  Widget build(BuildContext context) {
    final entradas = movimentacoes
        .where((m) => m.tipo == TipoMovimentacao.entrada)
        .length;
    final saidas = movimentacoes.length - entradas;

    final hoje = DateTime.now();
    final contagemPorDia = <DateTime, int>{};
    for (final mov in movimentacoes) {
      final dia = DateTime(mov.data.year, mov.data.month, mov.data.day);
      if (hoje.difference(dia).inDays > 13) continue;
      contagemPorDia[dia] = (contagemPorDia[dia] ?? 0) + 1;
    }
    final dias = contagemPorDia.keys.toList()..sort();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: _Estatistica(
                icone: Icons.south_west,
                cor: Cores.campo600,
                valor: '$entradas',
                rotulo: 'Entradas',
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _Estatistica(
                icone: Icons.north_east,
                cor: Cores.terra700,
                valor: '$saidas',
                rotulo: 'Saídas',
              ),
            ),
          ],
        ),
        if (dias.length >= 4) ...[
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Movimentações por dia (últimos 14 dias)',
                    style: Theme.of(
                      context,
                    ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 12),
                  SizedBox(
                    height: 100,
                    child: BarChart(
                      BarChartData(
                        titlesData: const FlTitlesData(show: false),
                        gridData: const FlGridData(show: false),
                        borderData: FlBorderData(show: false),
                        barTouchData: const BarTouchData(enabled: false),
                        barGroups: [
                          for (final (i, dia) in dias.indexed)
                            BarChartGroupData(
                              x: i,
                              barRods: [
                                BarChartRodData(
                                  toY: contagemPorDia[dia]!.toDouble(),
                                  color: Cores.campo600,
                                  width: 12,
                                  borderRadius: BorderRadius.circular(4),
                                ),
                              ],
                            ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ],
    );
  }
}

class _Estatistica extends StatelessWidget {
  const _Estatistica({
    required this.icone,
    required this.cor,
    required this.valor,
    required this.rotulo,
  });

  final IconData icone;
  final Color cor;
  final String valor;
  final String rotulo;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircleAvatar(
              backgroundColor: cor.withValues(alpha: 0.12),
              foregroundColor: cor,
              child: Icon(icone),
            ),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(valor, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                Text(rotulo, style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _FiltroDeTipo extends StatelessWidget {
  const _FiltroDeTipo({required this.selecionado, required this.aoMudar});

  final TipoMovimentacao? selecionado;
  final ValueChanged<TipoMovimentacao?> aoMudar;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        ChoiceChip(
          label: const Text('Todas'),
          selected: selecionado == null,
          onSelected: (_) => aoMudar(null),
        ),
        ChoiceChip(
          avatar: const Icon(Icons.south_west, size: 18),
          label: const Text('Entradas'),
          selected: selecionado == TipoMovimentacao.entrada,
          onSelected: (_) => aoMudar(TipoMovimentacao.entrada),
        ),
        ChoiceChip(
          avatar: const Icon(Icons.north_east, size: 18),
          label: const Text('Saídas'),
          selected: selecionado == TipoMovimentacao.saida,
          onSelected: (_) => aoMudar(TipoMovimentacao.saida),
        ),
      ],
    );
  }
}

class _CartaoDeMovimentacao extends StatelessWidget {
  const _CartaoDeMovimentacao({required this.mov, required this.insumo});

  final Movimentacao mov;
  final Insumo? insumo;

  @override
  Widget build(BuildContext context) {
    final entrada = mov.tipo == TipoMovimentacao.entrada;
    final cor = entrada ? Cores.campo600 : Cores.terra700;
    return Card(
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
        trailing: Text(
          '${entrada ? '+' : '−'}${formatarQuantidade(mov.quantidade)} '
          '${insumo?.unidade ?? ''}',
          style: TextStyle(color: cor, fontWeight: FontWeight.w700),
        ),
      ),
    );
  }
}
