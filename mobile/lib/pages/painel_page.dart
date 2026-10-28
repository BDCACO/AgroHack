import 'package:flutter/material.dart';

import '../core/servicos.dart';
import '../core/tema.dart';
import '../models/api.dart';
import '../widgets/aparece_em_cascata.dart';
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

        final porGravidade = <Gravidade, int>{};
        for (final (_, alerta) in alertas) {
          porGravidade[alerta.gravidade] = (porGravidade[alerta.gravidade] ?? 0) + 1;
        }

        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final gravidade in Gravidade.values)
                  if (porGravidade[gravidade] != null)
                    _ResumoDeGravidade(
                      gravidade: gravidade,
                      quantidade: porGravidade[gravidade]!,
                    ),
              ],
            ),
            const SizedBox(height: 16),
            ApareceEmCascata(
              indice: 0,
              child: Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _DestaqueDeAlerta(insumo: alertas.first.$1, alerta: alertas.first.$2),
              ),
            ),
            for (final (i, par) in alertas.skip(1).indexed)
              ApareceEmCascata(
                indice: i + 1,
                child: Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: _CartaoDeAlerta(insumo: par.$1, alerta: par.$2),
                ),
              ),
          ],
        );
      },
    );
  }
}

/// O alerta mais urgente de todos: não fica igual aos outros na lista, pra
/// não precisar ler linha por linha pra saber o que resolver primeiro.
class _DestaqueDeAlerta extends StatelessWidget {
  const _DestaqueDeAlerta({required this.insumo, required this.alerta});

  final Insumo insumo;
  final Alerta alerta;

  @override
  Widget build(BuildContext context) {
    final cor = alerta.gravidade.corTexto;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: cor,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: cor.withValues(alpha: 0.35),
            blurRadius: 16,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.priority_high, color: Colors.white, size: 18),
              const SizedBox(width: 6),
              Text(
                alerta.gravidade.texto,
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w700,
                  fontSize: 13,
                  letterSpacing: 0.4,
                ),
              ),
              Text(
                ' · resolva primeiro',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.85),
                  fontSize: 13,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            '${alerta.tipo.rotulo} · ${insumo.nome}',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 20,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            alerta.justificativa,
            style: TextStyle(color: Colors.white.withValues(alpha: 0.92), fontSize: 16),
          ),
        ],
      ),
    );
  }
}

class _ResumoDeGravidade extends StatelessWidget {
  const _ResumoDeGravidade({required this.gravidade, required this.quantidade});

  final Gravidade gravidade;
  final int quantidade;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: gravidade.cor.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(color: gravidade.cor, shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Text(
            '$quantidade ${gravidade.texto}',
            style: TextStyle(
              color: gravidade.corTexto,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class _CartaoDeAlerta extends StatelessWidget {
  const _CartaoDeAlerta({required this.insumo, required this.alerta});

  final Insumo insumo;
  final Alerta alerta;

  @override
  Widget build(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(width: 4, color: alerta.gravidade.cor),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Text(
                            '${alerta.tipo.rotulo} · ${insumo.nome}',
                            style: const TextStyle(fontWeight: FontWeight.w600),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color: alerta.gravidade.cor.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text(
                            alerta.gravidade.texto,
                            style: TextStyle(
                              color: alerta.gravidade.corTexto,
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      alerta.justificativa,
                      style: Theme.of(context).textTheme.bodyLarge,
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
