import 'package:flutter/material.dart';

import '../core/api/cliente_api.dart';
import '../core/tema.dart';
import 'esqueleto.dart';

/// Busca os dados de uma tela e cuida do que é igual em todas: carregando,
/// erro com "tentar de novo" e puxar para atualizar.
class CarregarDados<T> extends StatefulWidget {
  const CarregarDados({
    super.key,
    required this.buscar,
    required this.construir,
  });

  final Future<T> Function() buscar;
  final Widget Function(BuildContext context, T dados) construir;

  @override
  State<CarregarDados<T>> createState() => _CarregarDadosState<T>();
}

class _CarregarDadosState<T> extends State<CarregarDados<T>> {
  late Future<T> _carregando = widget.buscar();
  T? _dados;

  // Puxar para atualizar não troca a tela por um spinner: mantém os dados
  // antigos à vista e só avisa, por SnackBar, se a atualização falhar.
  Future<void> _recarregar() async {
    try {
      final dados = await widget.buscar();
      if (mounted) setState(() => _dados = dados);
    } catch (erro) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(erro is ApiError ? erro.mensagem : 'Algo deu errado.'),
        ),
      );
    }
  }

  void _tentarDeNovo() => setState(() => _carregando = widget.buscar());

  @override
  Widget build(BuildContext context) {
    final dados = _dados;
    if (dados != null) {
      return RefreshIndicator(
        onRefresh: _recarregar,
        child: widget.construir(context, dados),
      );
    }
    return FutureBuilder<T>(
      future: _carregando,
      builder: (context, estado) {
        final Widget filho;
        if (estado.connectionState != ConnectionState.done) {
          filho = const _EsqueletoDeLista(key: ValueKey('carregando'));
        } else if (estado.hasError) {
          final erro = estado.error;
          filho = _Erro(
            key: const ValueKey('erro'),
            mensagem: erro is ApiError ? erro.mensagem : 'Algo deu errado.',
            tentarDeNovo: _tentarDeNovo,
          );
        } else {
          _dados = estado.data;
          filho = RefreshIndicator(
            key: const ValueKey('dados'),
            onRefresh: _recarregar,
            child: widget.construir(context, estado.data as T),
          );
        }
        return AnimatedSwitcher(
          duration: const Duration(milliseconds: 200),
          child: filho,
        );
      },
    );
  }
}

class _Erro extends StatelessWidget {
  const _Erro({super.key, required this.mensagem, required this.tentarDeNovo});

  final String mensagem;
  final VoidCallback tentarDeNovo;

  @override
  Widget build(BuildContext context) {
    // SingleChildScrollView em vez de só Center: numa tela baixa (teclado
    // aberto, janela pequena) o Column não estoura, rola em vez de quebrar.
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(mensagem, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: tentarDeNovo,
              child: const Text('Tentar de novo'),
            ),
          ],
        ),
      ),
    );
  }
}

/// A forma de uma lista de cartões, antes dos dados chegarem — como os
/// `.esqueleto` do PainelPage/InsumoPage do site, só que genérico o
/// bastante pra servir pra qualquer tela daqui.
class _EsqueletoDeLista extends StatelessWidget {
  const _EsqueletoDeLista({super.key});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      physics: const NeverScrollableScrollPhysics(),
      children: [
        for (var i = 0; i < 5; i++)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    const Esqueleto(width: 40, height: 40, borderRadius: 20),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Esqueleto(width: i.isEven ? 160 : 120, height: 14),
                          const SizedBox(height: 8),
                          const Esqueleto(width: 80, height: 12),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }
}

/// Lista vazia que ainda deixa puxar para atualizar — ícone em anéis, título
/// e texto, como o EstadoVazio.vue do site, em vez de uma frase solta.
class EstadoVazio extends StatelessWidget {
  const EstadoVazio({
    super.key,
    required this.icone,
    required this.titulo,
    required this.texto,
  });

  final IconData icone;
  final String titulo;
  final String texto;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 56),
      children: [
        Stack(
          alignment: Alignment.center,
          children: [
            Container(
              width: 96,
              height: 96,
              decoration: const BoxDecoration(
                color: Cores.campo50,
                shape: BoxShape.circle,
              ),
            ),
            Container(
              width: 72,
              height: 72,
              decoration: const BoxDecoration(
                color: Cores.campo100,
                shape: BoxShape.circle,
              ),
            ),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: Colors.white,
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.08),
                    blurRadius: 4,
                  ),
                ],
              ),
              child: Icon(icone, size: 28, color: Cores.campo600),
            ),
          ],
        ),
        const SizedBox(height: 20),
        Text(
          titulo,
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 6),
        Text(
          texto,
          textAlign: TextAlign.center,
          style: const TextStyle(color: Colors.black54, height: 1.4),
        ),
      ],
    );
  }
}
