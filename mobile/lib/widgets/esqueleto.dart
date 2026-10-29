import 'package:flutter/material.dart';

/// Bloco "carregando": a forma do conteúdo, antes do conteúdo — como o
/// `.esqueleto` + `animate-brilho` do site (opacidade pulsando, 1,4 s).
class Esqueleto extends StatefulWidget {
  const Esqueleto({
    super.key,
    this.width,
    required this.height,
    this.borderRadius = 8,
  });

  final double? width;
  final double height;
  final double borderRadius;

  @override
  State<Esqueleto> createState() => _EsqueletoState();
}

class _EsqueletoState extends State<Esqueleto>
    with SingleTickerProviderStateMixin {
  // Metade do ciclo: repeat(reverse: true) vai e volta, então 700ms de ida +
  // 700ms de volta fecham os 1,4s do keyframe original.
  late final _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 700),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const base = Color(0xFFE7E5E4); // stone-200
    if (MediaQuery.of(context).disableAnimations) {
      return _caixa(base.withValues(alpha: 0.7));
    }
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) =>
          _caixa(base.withValues(alpha: 0.7 - 0.35 * _controller.value)),
    );
  }

  Widget _caixa(Color cor) => Container(
    width: widget.width,
    height: widget.height,
    decoration: BoxDecoration(
      color: cor,
      borderRadius: BorderRadius.circular(widget.borderRadius),
    ),
  );
}
