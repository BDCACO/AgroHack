import 'package:flutter/material.dart';

import '../core/servicos.dart';
import '../core/tema.dart';
import '../models/api.dart';
import '../widgets/aparece_em_cascata.dart';
import '../widgets/carregar_dados.dart';
import '../widgets/resumo_gravidade.dart';

String _saudacao() {
  final hora = DateTime.now().hour;
  if (hora < 12) return 'Bom dia';
  if (hora < 18) return 'Boa tarde';
  return 'Boa noite';
}

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
          porGravidade[alerta.gravidade] =
              (porGravidade[alerta.gravidade] ?? 0) + 1;
        }

        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              _saudacao(),
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.bold,
                color: Cores.campo800,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              'Veja o que precisa de atenção na lavoura hoje.',
              style: Theme.of(context).textTheme.bodyMedium
                  ?.copyWith(color: Colors.black54),
            ),
            const SizedBox(height: 20),
            FaixaDeResumo(porGravidade: porGravidade),
            const SizedBox(height: 16),
            ApareceEmCascata(
              indice: 0,
              child: Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _DestaqueDeAlerta(
                  insumo: alertas.first.$1,
                  alerta: alertas.first.$2,
                ),
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
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [cor, Color.lerp(cor, Colors.black, 0.18)!],
        ),
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: cor.withValues(alpha: 0.35),
            blurRadius: 20,
            offset: const Offset(0, 8),
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
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.92),
              fontSize: 16,
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
