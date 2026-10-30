import 'package:flutter/material.dart';

import '../core/tema.dart';

/// Pisca o fundo do filho quando [ativo] vira true, e esmaece de volta — como
/// o `.animate-destaque` do site, para marcar a linha que acabou de mudar.
class Destaque extends StatefulWidget {
  const Destaque({super.key, required this.ativo, required this.child});

  final bool ativo;
  final Widget child;

  @override
  State<Destaque> createState() => _DestaqueState();
}

class _DestaqueState extends State<Destaque>
    with SingleTickerProviderStateMixin {
  // Em repouso (nunca ativado, ou já esmaecido) o valor é 0: sem tingir nada.
  // Ativar pula direto para 1 (o tingido) e anima de volta a 0 — o "pisca e
  // some", não um crescendo.
  late final _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1600),
  );

  void _piscar() {
    _controller.value = 1;
    _controller.animateTo(0, curve: Curves.easeOut);
  }

  @override
  void initState() {
    super.initState();
    if (widget.ativo) _piscar();
  }

  @override
  void didUpdateWidget(covariant Destaque oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.ativo && !oldWidget.ativo) _piscar();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (MediaQuery.of(context).disableAnimations) return widget.child;
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) => ColoredBox(
        key: const ValueKey('destaque'),
        color:
            Color.lerp(Colors.transparent, Cores.campo100, _controller.value) ??
            Colors.transparent,
        child: child,
      ),
      child: widget.child,
    );
  }
}
