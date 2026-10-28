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
      construir: (context, prontidao) => ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ApareceEmCascata(
            indice: 0,
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
            indice: 1,
            child: Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: _CartaoDeStatus(
                icone: prontidao.bancoOk ? Icons.storage : Icons.error_outline,
                titulo: 'Banco de dados',
                status: prontidao.bancoOk ? 'Conectado' : 'Com erro',
                ok: prontidao.bancoOk,
              ),
            ),
          ),
          ApareceEmCascata(
            indice: 2,
            child: Card(
              child: ListTile(
                leading: const Icon(Icons.link),
                title: const Text('Endereço da API'),
                subtitle: const Text(urlDaApi),
              ),
            ),
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
    final cor = ok ? Cores.campo600 : const Color(0xFFDC2626);
    return Card(
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: cor.withValues(alpha: 0.12),
          foregroundColor: cor,
          child: Icon(icone),
        ),
        title: Text(titulo),
        subtitle: Text(
          status,
          style: TextStyle(color: cor, fontWeight: FontWeight.w600),
        ),
      ),
    );
  }
}
