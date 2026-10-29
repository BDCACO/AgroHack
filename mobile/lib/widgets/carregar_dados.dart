import 'package:flutter/material.dart';

import '../core/api/cliente_api.dart';

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
          filho = const Center(
            key: ValueKey('carregando'),
            child: CircularProgressIndicator(),
          );
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

/// Lista vazia que ainda deixa puxar para atualizar.
class EstadoVazio extends StatelessWidget {
  const EstadoVazio(this.texto, {super.key});

  final String texto;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(32),
      children: [Text(texto, textAlign: TextAlign.center)],
    );
  }
}
