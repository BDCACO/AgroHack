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
  late Future<T> _dados = widget.buscar();

  Future<void> _recarregar() {
    final dados = widget.buscar();
    setState(() => _dados = dados);
    return dados.then((_) {}, onError: (_) {});
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<T>(
      future: _dados,
      builder: (context, estado) {
        if (estado.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (estado.hasError) {
          final erro = estado.error;
          return _Erro(
            mensagem: erro is ApiError ? erro.mensagem : 'Algo deu errado.',
            tentarDeNovo: _recarregar,
          );
        }
        return RefreshIndicator(
          onRefresh: _recarregar,
          child: widget.construir(context, estado.data as T),
        );
      },
    );
  }
}

class _Erro extends StatelessWidget {
  const _Erro({required this.mensagem, required this.tentarDeNovo});

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
