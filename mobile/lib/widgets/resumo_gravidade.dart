import 'package:flutter/material.dart';

import '../core/tema.dart';
import '../models/api.dart';

/// Uma pílula "3 Urgente" — usada no Painel e em Insumos pra dar o resumo
/// antes de rolar a lista inteira.
class ResumoDeGravidade extends StatelessWidget {
  const ResumoDeGravidade({
    super.key,
    required this.gravidade,
    required this.quantidade,
  });

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
            style: TextStyle(color: gravidade.corTexto, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}

/// Conta os insumos/alertas por gravidade e mostra uma fileira de
/// [ResumoDeGravidade], só com as gravidades que aparecem de fato.
class FaixaDeResumo extends StatelessWidget {
  const FaixaDeResumo({super.key, required this.porGravidade});

  final Map<Gravidade, int> porGravidade;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final gravidade in Gravidade.values)
          if (porGravidade[gravidade] != null)
            ResumoDeGravidade(
              gravidade: gravidade,
              quantidade: porGravidade[gravidade]!,
            ),
      ],
    );
  }
}
