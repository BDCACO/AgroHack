import 'package:flutter/material.dart';

import '../core/api/cliente_api.dart';
import '../core/servicos.dart';
import '../models/api.dart';
import '../widgets/carregar_dados.dart';
import '../widgets/formato.dart';

/// Formulário de uma movimentação nova: tipo, insumo, quantidade e, se houver,
/// a validade do lote. Mesmos campos do POST /movimentacoes do site.
class LancarMovimentacaoPage extends StatelessWidget {
  const LancarMovimentacaoPage({super.key});

  @override
  Widget build(BuildContext context) {
    final estoque = Servicos.of(context).estoque;
    return Scaffold(
      appBar: AppBar(title: const Text('Lançar movimentação')),
      body: CarregarDados<List<Insumo>>(
        buscar: estoque.listarInsumos,
        construir: (context, insumos) => _Formulario(insumos: insumos),
      ),
    );
  }
}

class _Formulario extends StatefulWidget {
  const _Formulario({required this.insumos});

  final List<Insumo> insumos;

  @override
  State<_Formulario> createState() => _FormularioState();
}

class _FormularioState extends State<_Formulario> {
  final _formKey = GlobalKey<FormState>();
  final _quantidadeController = TextEditingController();
  var _tipo = TipoMovimentacao.entrada;
  Insumo? _insumo;
  var _data = DateTime.now();
  DateTime? _validade;
  var _enviando = false;

  @override
  void dispose() {
    _quantidadeController.dispose();
    super.dispose();
  }

  Future<void> _lancar() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _enviando = true);
    final dados = MovimentacaoEntrada(
      insumoId: _insumo!.id,
      tipo: _tipo,
      data: _data,
      quantidade: double.parse(
        _quantidadeController.text.replaceAll(',', '.'),
      ),
      validade: _validade,
    );
    final servicos = Servicos.of(context);
    try {
      await servicos.estoque.registrarMovimentacao(dados);
      if (mounted) Navigator.pop(context, 'ok');
    } catch (erro) {
      // Sem resposta da API: guarda para enviar quando a rede voltar, em vez
      // de fazer a pessoa perder o que já preencheu.
      if (erro is ApiError && erro.status == null) {
        await servicos.pendencias.adicionar(dados);
        if (mounted) Navigator.pop(context, 'offline');
        return;
      }
      if (!mounted) return;
      setState(() => _enviando = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(erro is ApiError ? erro.mensagem : 'Algo deu errado.'),
        ),
      );
    }
  }

  Future<void> _escolherData({required bool validade}) async {
    final escolhida = await showDatePicker(
      context: context,
      initialDate: validade ? (_validade ?? DateTime.now()) : _data,
      firstDate: DateTime(2000),
      lastDate: DateTime(2100),
    );
    if (escolhida == null || !mounted) return;
    setState(() => validade ? _validade = escolhida : _data = escolhida);
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          SegmentedButton<TipoMovimentacao>(
            segments: const [
              ButtonSegment(
                value: TipoMovimentacao.entrada,
                label: Text('Entrada'),
                icon: Icon(Icons.south_west),
              ),
              ButtonSegment(
                value: TipoMovimentacao.saida,
                label: Text('Saída'),
                icon: Icon(Icons.north_east),
              ),
            ],
            selected: {_tipo},
            onSelectionChanged: (selecao) =>
                setState(() => _tipo = selecao.first),
          ),
          const SizedBox(height: 16),
          DropdownButtonFormField<Insumo>(
            initialValue: _insumo,
            decoration: const InputDecoration(labelText: 'Insumo'),
            items: [
              for (final insumo in widget.insumos)
                DropdownMenuItem(value: insumo, child: Text(insumo.nome)),
            ],
            onChanged: (insumo) => setState(() => _insumo = insumo),
            validator: (insumo) => insumo == null ? 'Escolha um insumo' : null,
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _quantidadeController,
            decoration: InputDecoration(
              labelText: 'Quantidade',
              suffixText: _insumo?.unidade,
            ),
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            validator: (texto) {
              final valor = double.tryParse(
                (texto ?? '').replaceAll(',', '.'),
              );
              return valor == null || valor <= 0
                  ? 'Informe uma quantidade válida'
                  : null;
            },
          ),
          const SizedBox(height: 16),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Data'),
            subtitle: Text(formatarData(_data)),
            trailing: const Icon(Icons.calendar_today_outlined),
            onTap: () => _escolherData(validade: false),
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Validade do lote (opcional)'),
            subtitle: Text(
              _validade == null ? 'Sem validade' : formatarData(_validade!),
            ),
            trailing: _validade == null
                ? const Icon(Icons.calendar_today_outlined)
                : IconButton(
                    icon: const Icon(Icons.clear),
                    onPressed: () => setState(() => _validade = null),
                  ),
            onTap: () => _escolherData(validade: true),
          ),
          const SizedBox(height: 24),
          FilledButton(
            onPressed: _enviando ? null : _lancar,
            child: _enviando
                ? const SizedBox(
                    height: 20,
                    width: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Lançar'),
          ),
        ],
      ),
    );
  }
}
