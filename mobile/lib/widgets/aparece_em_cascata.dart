import 'package:flutter/material.dart';

/// Anima a entrada de um item de lista: desliza de baixo pra cima e some o
/// fade, um pouco depois do item anterior — dá a sensação de cascata.
class ApareceEmCascata extends StatefulWidget {
  const ApareceEmCascata({super.key, required this.indice, required this.child});

  final int indice;
  final Widget child;

  @override
  State<ApareceEmCascata> createState() => _ApareceEmCascataState();
}

class _ApareceEmCascataState extends State<ApareceEmCascata> {
  var _visivel = false;

  @override
  void initState() {
    super.initState();
    // Além de 10 itens o atraso para de crescer: a lista não devia "gaguejar"
    // até o fim ao rolar rápido.
    final atraso = 40 * widget.indice.clamp(0, 10);
    Future.delayed(Duration(milliseconds: atraso), () {
      if (mounted) setState(() => _visivel = true);
    });
  }

  @override
  Widget build(BuildContext context) {
    // "Reduzir movimento" do sistema: mostra direto, sem cascata nenhuma.
    if (MediaQuery.of(context).disableAnimations) return widget.child;
    return AnimatedSlide(
      offset: _visivel ? Offset.zero : const Offset(0, 0.08),
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeOut,
      child: AnimatedOpacity(
        opacity: _visivel ? 1 : 0,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
        child: widget.child,
      ),
    );
  }
}
