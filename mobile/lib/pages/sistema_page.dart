import 'package:flutter/material.dart';

import '../core/config.dart';
import '../core/servicos.dart';
import '../core/tema.dart';
import '../models/api.dart';
import '../widgets/aparece_em_cascata.dart';
import '../widgets/carregar_dados.dart';

/// A situação da API e do banco: a verificação de que o app chega até eles.
class SistemaPage extends StatelessWidget {
  const SistemaPage({super.key});

  @override
  Widget build(BuildContext context) {
    final health = Servicos.of(context).health;
    return CarregarDados<ReadinessResponse>(
      buscar: health.buscarReadiness,
      construir: (context, prontidao) {
        final tudoOk = prontidao.pronto && prontidao.bancoOk;
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            ApareceEmCascata(indice: 0, child: _ResumoGeral(tudoOk: tudoOk)),
            const SizedBox(height: 16),
            ApareceEmCascata(
              indice: 1,
              child: Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: _CartaoDeStatus(
                  icone: Icons.cloud_done_outlined,
                  titulo: 'API',
                  status: prontidao.pronto ? 'No ar' : 'Indisponível',
                  ok: prontidao.pronto,
                ),
              ),
            ),
            ApareceEmCascata(
              indice: 2,
              child: _CartaoDeStatus(
                icone: prontidao.bancoOk ? Icons.storage : Icons.error_outline,
                titulo: 'Banco de dados',
                status: prontidao.bancoOk ? 'Conectado' : 'Com erro',
                ok: prontidao.bancoOk,
              ),
            ),
            ApareceEmCascata(
              indice: 3,
              child: const Padding(
                padding: EdgeInsets.only(top: 8),
                child: _ModoSolForte(),
              ),
            ),
            ApareceEmCascata(
              indice: 4,
              child: Padding(
                padding: const EdgeInsets.only(top: 16),
                child: Row(
                  children: [
                    Icon(
                      Icons.link,
                      size: 16,
                      color: Theme.of(context).colorScheme.outline,
                    ),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        urlDaApi,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.outline,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

/// Liga/desliga o modo sol forte: bordas sólidas e fundo sem translucidez,
/// pensado pra usar no brilho direto do meio-dia, não pra ambiente escuro.
class _ModoSolForte extends StatelessWidget {
  const _ModoSolForte();

  @override
  Widget build(BuildContext context) {
    final notificador = Servicos.of(context).solForte;
    return ValueListenableBuilder<bool>(
      valueListenable: notificador,
      builder: (context, ligado, _) => Card(
        child: SwitchListTile(
          secondary: const Icon(Icons.wb_sunny_outlined),
          title: const Text('Modo sol forte'),
          subtitle: const Text(
            'Bordas sólidas e mais contraste, pra enxergar a tela no sol do '
            'meio-dia.',
          ),
          value: ligado,
          onChanged: (valor) => notificador.value = valor,
        ),
      ),
    );
  }
}

/// O que importa pra quem não vai ler duas linhas técnicas: tá tudo bem ou não.
class _ResumoGeral extends StatelessWidget {
  const _ResumoGeral({required this.tudoOk});

  final bool tudoOk;

  @override
  Widget build(BuildContext context) {
    final cor = tudoOk ? Cores.campo600 : const Color(0xFFB91C1C);
    final corDoConteudo = corDoIcone(context, cor);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 28, horizontal: 16),
      decoration: BoxDecoration(
        color: fundoDoCirculo(context, cor),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        children: [
          Icon(
            tudoOk ? Icons.check_circle : Icons.error,
            color: corDoConteudo,
            size: 56,
          ),
          const SizedBox(height: 12),
          Text(
            tudoOk ? 'Tudo funcionando' : 'Tem algo errado',
            style: Theme.of(context).textTheme.titleLarge
                ?.copyWith(color: corDoConteudo, fontWeight: FontWeight.bold),
          ),
        ],
      ),
    );
  }
}

class _CartaoDeStatus extends StatelessWidget {
  const _CartaoDeStatus({
    required this.icone,
    required this.titulo,
    required this.status,
    required this.ok,
  });

  final IconData icone;
  final String titulo;
  final String status;
  final bool ok;

  @override
  Widget build(BuildContext context) {
    final cor = ok ? Cores.campo600 : const Color(0xFFB91C1C);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Card(
        child: ListTile(
          leading: CircleAvatar(
            backgroundColor: fundoDoCirculo(context, cor),
            foregroundColor: corDoIcone(context, cor),
            child: Icon(icone),
          ),
          title: Text(
            titulo,
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
          subtitle: Text(
            status,
            style: TextStyle(color: cor, fontWeight: FontWeight.w600),
          ),
        ),
      ),
    );
  }
}
