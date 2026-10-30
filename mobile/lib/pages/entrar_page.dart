import 'package:flutter/material.dart';

import '../core/api/cliente_api.dart';
import '../core/servicos.dart';
import '../models/api.dart';

/// Tela de entrada: pede login e senha. Mesmos campos do
/// frontend/src/pages/EntrarPage.vue.
class EntrarPage extends StatefulWidget {
  const EntrarPage({super.key, required this.aoEntrar});

  /// Chamado com a sessão criada; quem constrói esta tela guarda o token e
  /// troca para as telas principais.
  final Future<void> Function(Entrada) aoEntrar;

  @override
  State<EntrarPage> createState() => _EntrarPageState();
}

class _EntrarPageState extends State<EntrarPage> {
  final _formKey = GlobalKey<FormState>();
  final _loginController = TextEditingController();
  final _senhaController = TextEditingController();
  var _entrando = false;
  String? _erro;

  @override
  void dispose() {
    _loginController.dispose();
    _senhaController.dispose();
    super.dispose();
  }

  Future<void> _entrar() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _entrando = true;
      _erro = null;
    });
    try {
      final entrada = await Servicos.of(context).auth.entrar(
        _loginController.text.trim(),
        _senhaController.text,
      );
      await widget.aoEntrar(entrada);
    } catch (erro) {
      setState(() {
        _erro = erro is ApiError ? erro.mensagem : 'Não deu pra entrar.';
        _senhaController.clear();
      });
    } finally {
      if (mounted) setState(() => _entrando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 360),
              child: Form(
                key: _formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      'CampoCerto',
                      textAlign: TextAlign.center,
                      style: Theme.of(
                        context,
                      ).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Entre para continuar',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                    const SizedBox(height: 32),
                    TextFormField(
                      controller: _loginController,
                      autofocus: true,
                      decoration: const InputDecoration(labelText: 'Login'),
                      textInputAction: TextInputAction.next,
                      validator: (texto) =>
                          (texto ?? '').trim().isEmpty ? 'Informe o login' : null,
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _senhaController,
                      decoration: const InputDecoration(labelText: 'Senha'),
                      obscureText: true,
                      textInputAction: TextInputAction.done,
                      onFieldSubmitted: (_) => _entrar(),
                      validator: (texto) =>
                          (texto ?? '').isEmpty ? 'Informe a senha' : null,
                    ),
                    if (_erro != null) ...[
                      const SizedBox(height: 16),
                      Text(
                        _erro!,
                        style: TextStyle(color: Theme.of(context).colorScheme.error),
                      ),
                    ],
                    const SizedBox(height: 24),
                    FilledButton(
                      onPressed: _entrando ? null : _entrar,
                      child: _entrando
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('Entrar'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
