import 'package:flutter/material.dart';

import '../core/servicos.dart';
import '../core/tema.dart';
import '../models/api.dart';
import '../widgets/aparece_em_cascata.dart';
import '../widgets/carregar_dados.dart';
import '../widgets/formato.dart';
import '../widgets/resumo_gravidade.dart';

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

        final maisGraves = [
          for (final insumo in insumos)
            insumo.analise.alertas
                .map((alerta) => alerta.gravidade)
                .fold<Gravidade?>(
                  null,
                  (pior, g) => pior == null || g.index < pior.index ? g : pior,
                ),
        ];
        final porGravidade = <Gravidade, int>{};
        for (final g in maisGraves.nonNulls) {
          porGravidade[g] = (porGravidade[g] ?? 0) + 1;
        }

        return ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: insumos.length + (porGravidade.isEmpty ? 0 : 1),
          itemBuilder: (context, i) {
            if (porGravidade.isNotEmpty) {
              if (i == 0) {
                return Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: FaixaDeResumo(porGravidade: porGravidade),
                );
              }
              i -= 1;
            }
            final insumo = insumos[i];
            return ApareceEmCascata(
              indice: i,
              child: Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: _CartaoDeInsumo(insumo: insumo, maisGrave: maisGraves[i]),
              ),
            );
          },
        );
      },
    );
  }
}

class _CartaoDeInsumo extends StatelessWidget {
  const _CartaoDeInsumo({required this.insumo, required this.maisGrave});

  final Insumo insumo;
  final Gravidade? maisGrave;

  @override
  Widget build(BuildContext context) {
    final cor = maisGrave?.cor ?? Cores.campo600;
    final corTexto = maisGrave?.corTexto ?? Cores.campo800;
    final minimo = insumo.estoqueMinimo;
    // Até 1.5x o mínimo enche a barra: dá pra ver "folga" sem estourar o traço
    // só porque o estoque está bem acima do ponto de pedir mais.
    final proporcao = (minimo == null || minimo <= 0)
        ? null
        : (insumo.estoqueAtual / minimo / 1.5).clamp(0.0, 1.0);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            CircleAvatar(
              backgroundColor: cor.withValues(alpha: 0.12),
              foregroundColor: cor,
              child: Icon(iconeDaUnidade(insumo.unidade)),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          insumo.nome,
                          style: const TextStyle(
                            fontWeight: FontWeight.w600,
                            fontSize: 16,
                          ),
                        ),
                      ),
                      Text(
                        '${formatarQuantidade(insumo.estoqueAtual)} ${insumo.unidade}',
                        style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    maisGrave == null ? 'Sem alertas' : maisGrave!.texto,
                    style: TextStyle(
                      color: corTexto,
                      fontWeight: FontWeight.w600,
                      fontSize: 13,
                    ),
                  ),
                  if (proporcao != null) ...[
                    const SizedBox(height: 10),
                    // Enche a barra até o valor real em vez de já aparecer
                    // pronta — fica claro que é uma medida, não um enfeite.
                    TweenAnimationBuilder<double>(
                      tween: Tween(begin: 0, end: proporcao),
                      duration: const Duration(milliseconds: 600),
                      curve: Curves.easeOutCubic,
                      builder: (context, valor, _) => ClipRRect(
                        borderRadius: BorderRadius.circular(999),
                        child: LinearProgressIndicator(
                          value: valor,
                          minHeight: 6,
                          backgroundColor: cor.withValues(alpha: 0.15),
                          valueColor: AlwaysStoppedAnimation(cor),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
