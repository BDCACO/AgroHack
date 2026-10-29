import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../core/servicos.dart';
import '../core/tema.dart';
import '../models/api.dart';
import '../services/pendencias.dart';
import '../widgets/aparece_em_cascata.dart';
import '../widgets/carregar_dados.dart';
import '../widgets/destaque.dart';
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
  TipoMovimentacao? _filtro;
  // A que acabou de ser lançada: pisca na lista, igual ao site.
  int? _destacada;

  Map<DateTime, List<Movimentacao>> _agruparPorDia(List<Movimentacao> lista) {
    final grupos = <DateTime, List<Movimentacao>>{};
    for (final mov in lista) {
      final dia = DateTime(mov.data.year, mov.data.month, mov.data.day);
      (grupos[dia] ??= []).add(mov);
    }
    return grupos;
  }

  Future<void> _lancar() async {
    final resultado = await Navigator.push<Object>(
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
    } else if (resultado is Movimentacao) {
      setState(() => _destacada = resultado.id);
      Future.delayed(const Duration(milliseconds: 1600), () {
        if (mounted) setState(() => _destacada = null);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final servicos = Servicos.of(context);
    return Scaffold(
      body:
          CarregarDados<
            (List<Movimentacao>, Map<int, Insumo>, List<Pendencia>)
          >(
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

              final filtradas = _filtro == null
                  ? movimentacoes
                  : movimentacoes.where((m) => m.tipo == _filtro).toList();
              final grupos = _agruparPorDia(filtradas);

              return ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (pendentes.isNotEmpty) ...[
                    for (final pendencia in pendentes)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: _ItemPendente(
                          pendencia: pendencia,
                          nomeDoInsumo:
                              insumos[pendencia.dados.insumoId]?.nome ??
                              'Insumo ${pendencia.dados.insumoId}',
                          onTentar: () async {
                            await servicos.pendencias.tentarEnviar(
                              apenas: pendencia.criadoEm,
                            );
                            if (mounted) setState(() => _versao++);
                          },
                          onDescartar: () async {
                            await servicos.pendencias.descartar(
                              pendencia.criadoEm,
                            );
                            if (mounted) setState(() => _versao++);
                          },
                        ),
                      ),
                    const SizedBox(height: 8),
                  ],
                  _ResumoDeMovimentacoes(movimentacoes: movimentacoes),
                  const SizedBox(height: 16),
                  _FiltroDeTipo(
                    selecionado: _filtro,
                    aoMudar: (tipo) => setState(() => _filtro = tipo),
                  ),
                  const SizedBox(height: 8),
                  // Trocar o filtro troca a lista inteira: crossfade pra ficar
                  // claro que foi a escolha que mudou o que aparece, não um bug.
                  AnimatedSwitcher(
                    duration: const Duration(milliseconds: 250),
                    switchInCurve: Curves.easeOut,
                    switchOutCurve: Curves.easeIn,
                    child: Column(
                      key: ValueKey(_filtro),
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        if (filtradas.isEmpty)
                          const Padding(
                            padding: EdgeInsets.symmetric(vertical: 32),
                            child: Center(
                              child: Text('Nada lançado com esse filtro.'),
                            ),
                          )
                        else
                          for (final grupo in grupos.entries) ...[
                            Padding(
                              padding: const EdgeInsets.fromLTRB(4, 12, 4, 8),
                              child: Text(
                                formatarDiaRelativo(grupo.key),
                                style: const TextStyle(
                                  fontWeight: FontWeight.w700,
                                  fontSize: 13,
                                ),
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
                                    destacada: mov.id == _destacada,
                                  ),
                                ),
                              ),
                          ],
                      ],
                    ),
                  ),
                ],
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
    return Card(
      child: ListTile(
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
      ),
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
                    style: Theme.of(context).textTheme.bodyMedium
                        ?.copyWith(fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 12),
                  SizedBox(
                    height: 100,
                    child: BarChart(
                      duration: const Duration(milliseconds: 400),
                      curve: Curves.easeOutCubic,
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
                Text(
                  valor,
                  style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
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
  const _CartaoDeMovimentacao({
    required this.mov,
    required this.insumo,
    this.destacada = false,
  });

  final Movimentacao mov;
  final Insumo? insumo;
  final bool destacada;

  @override
  Widget build(BuildContext context) {
    final entrada = mov.tipo == TipoMovimentacao.entrada;
    final cor = entrada ? Cores.campo600 : Cores.terra700;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Destaque(
        ativo: destacada,
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
      ),
    );
  }
}
