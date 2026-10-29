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
          _Ponto(cor: gravidade.cor, pulsar: gravidade == Gravidade.alta),
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

/// O ponto de gravidade; o "alta" ganha uma onda que cresce e some ao redor,
/// como o `after:animate-pulsar` do SeloDeGravidade.vue — chama o olho pro
/// que não pode esperar.
class _Ponto extends StatefulWidget {
  const _Ponto({required this.cor, required this.pulsar});

  final Color cor;
  final bool pulsar;

  @override
  State<_Ponto> createState() => _PontoState();
}

class _PontoState extends State<_Ponto> with SingleTickerProviderStateMixin {
  // Só algumas voltas, não para sempre: continua claro qual é o urgente sem
  // ficar piscando a tela toda a bateria do aparelho (e deixa a animação
  // terminar de verdade, para o pumpAndSettle dos testes).
  late final _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1600),
  )..repeat(count: 4);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final mostrarOnda =
        widget.pulsar && !MediaQuery.of(context).disableAnimations;
    return SizedBox(
      width: 20,
      height: 20,
      child: Stack(
        alignment: Alignment.center,
        children: [
          if (mostrarOnda)
            AnimatedBuilder(
              animation: _controller,
              builder: (context, _) => Opacity(
                opacity: (0.45 * (1 - _controller.value)).clamp(0, 1),
                child: Transform.scale(
                  scale: 1 + _controller.value * 2.7,
                  child: _bolinha(widget.cor),
                ),
              ),
            ),
          _bolinha(widget.cor),
        ],
      ),
    );
  }

  Widget _bolinha(Color cor) => Container(
    width: 8,
    height: 8,
    decoration: BoxDecoration(color: cor, shape: BoxShape.circle),
  );
}
