import 'package:flutter/material.dart';

import '../core/api/cliente_api.dart';
import '../core/servicos.dart';
import '../models/api.dart';
import '../services/codigo_de_barras.dart';
import '../widgets/carregar_dados.dart';
import '../widgets/formato.dart';
import 'leitor_de_codigo_de_barras_page.dart';

// Mesma unidade que entra em toda conta do insumo (estoque, consumo, reposição):
// uma lista fechada evita medidas confusas como "395g" (peso da embalagem, não
// uma unidade) digitadas por engano no cadastro pelo celular.
const _unidadesDeMedida = ['kg', 'g', 't', 'L', 'mL', 'un', 'sc', 'cx', 'lata', 'pct'];

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
  late final _insumos = List<Insumo>.of(widget.insumos);
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
      quantidade: double.parse(_quantidadeController.text.replaceAll(',', '.')),
      validade: _validade,
    );
    final servicos = Servicos.of(context);
    try {
      final criada = await servicos.estoque.registrarMovimentacao(dados);
      if (mounted) Navigator.pop(context, criada);
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

  Future<void> _lerCodigoDeBarras() async {
    final codigo = await Navigator.push<String>(
      context,
      MaterialPageRoute(builder: (_) => const LeitorDeCodigoDeBarrasPage()),
    );
    if (codigo == null || !mounted) return;

    final encontrado = insumoPeloCodigoDeBarras(_insumos, codigo);
    if (encontrado != null) {
      final confirmado = await showDialog<bool>(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('É esse o insumo?'),
          content: Text('Código encontrado: ${encontrado.nome}.'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Não'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Sim'),
            ),
          ],
        ),
      );
      if (confirmado == true && mounted) setState(() => _insumo = encontrado);
      return;
    }

    if (!mounted) return;
    var novo = false;
    final escolhido = await showModalBottomSheet<Insumo>(
      context: context,
      builder: (_) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text('Código não reconhecido. De qual insumo ele é?'),
            ),
            for (final insumo in _insumos)
              ListTile(
                title: Text(insumo.nome),
                onTap: () => Navigator.pop(context, insumo),
              ),
            const Divider(height: 1),
            ListTile(
              leading: const Icon(Icons.add_circle_outline),
              title: const Text('É um insumo novo'),
              onTap: () {
                novo = true;
                Navigator.pop(context);
              },
            ),
          ],
        ),
      ),
    );
    if (!mounted) return;
    if (escolhido != null) {
      setState(() => _insumo = escolhido);
      try {
        // Ensina o vínculo para a próxima leitura reconhecer sozinha; o
        // lançamento de agora não depende disso ter sucesso.
        await Servicos.of(context).estoque.atualizarInsumo(
          escolhido.id,
          InsumoCadastro(
            nome: escolhido.nome,
            unidade: escolhido.unidade,
            estoqueMinimo: escolhido.estoqueMinimo,
            prazoReposicaoDias: escolhido.prazoReposicaoDias,
            codigoDeBarras: codigo,
          ),
        );
      } catch (_) {
        // Sem internet ou API fora: tenta de novo na próxima leitura.
      }
      return;
    }
    if (novo) await _cadastrarInsumoNovo(codigo);
  }

  Future<void> _cadastrarInsumoNovo(String codigo) async {
    final nomeController = TextEditingController();
    final formKey = GlobalKey<FormState>();
    String? unidade;
    try {
      final confirmado = await showDialog<bool>(
        context: context,
        builder: (_) => StatefulBuilder(
          builder: (context, setDialogState) => AlertDialog(
            title: const Text('Insumo novo'),
            content: Form(
              key: formKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextFormField(
                    controller: nomeController,
                    decoration: const InputDecoration(labelText: 'Nome'),
                    validator: (texto) =>
                        (texto ?? '').trim().isEmpty ? 'Informe o nome' : null,
                  ),
                  DropdownButtonFormField<String>(
                    initialValue: unidade,
                    decoration: const InputDecoration(labelText: 'Unidade'),
                    items: [
                      for (final u in _unidadesDeMedida)
                        DropdownMenuItem(value: u, child: Text(u)),
                    ],
                    onChanged: (valor) =>
                        setDialogState(() => unidade = valor),
                    validator: (valor) =>
                        valor == null ? 'Escolha a unidade' : null,
                  ),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Cancelar'),
              ),
              FilledButton(
                onPressed: () {
                  if (formKey.currentState!.validate()) {
                    Navigator.pop(context, true);
                  }
                },
                child: const Text('Cadastrar'),
              ),
            ],
          ),
        ),
      );
      if (confirmado != true || !mounted) return;
      final criado = await Servicos.of(context).estoque.criarInsumo(
        InsumoCadastro(
          nome: nomeController.text.trim(),
          unidade: unidade!,
          codigoDeBarras: codigo,
        ),
      );
      if (!mounted) return;
      setState(() {
        _insumos.add(criado);
        _insumo = criado;
      });
    } catch (erro) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            erro is ApiError ? erro.mensagem : 'Não deu pra cadastrar o insumo.',
          ),
        ),
      );
    } finally {
      nomeController.dispose();
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
          OutlinedButton.icon(
            onPressed: _lerCodigoDeBarras,
            icon: const Icon(Icons.qr_code_scanner),
            label: const Text('Ler código de barras ou QR Code'),
          ),
          const SizedBox(height: 16),
          DropdownButtonFormField<Insumo>(
            initialValue: _insumo,
            decoration: const InputDecoration(labelText: 'Insumo'),
            items: [
              for (final insumo in _insumos)
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
              final valor = double.tryParse((texto ?? '').replaceAll(',', '.'));
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
