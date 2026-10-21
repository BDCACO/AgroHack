import '../core/api/cliente_api.dart';
import '../models/api.dart';

/// Chamadas da API de estoque. Mesmas rotas do frontend/src/services/estoque.ts.
class EstoqueService {
  const EstoqueService(this._api);

  final ClienteApi _api;

  Future<List<Insumo>> listarInsumos() async {
    final dados = await _api.get('/insumos') as List;
    return [for (final item in dados) Insumo.fromJson(item as Json)];
  }

  Future<InsumoDetalhe> buscarInsumo(int id) async =>
      InsumoDetalhe.fromJson(await _api.get('/insumos/$id') as Json);

  Future<Insumo> criarInsumo(InsumoCadastro dados) async =>
      Insumo.fromJson(await _api.post('/insumos', dados.toJson()) as Json);

  Future<Insumo> atualizarInsumo(int id, InsumoCadastro dados) async =>
      Insumo.fromJson(await _api.put('/insumos/$id', dados.toJson()) as Json);

  Future<void> removerInsumo(int id) => _api.delete('/insumos/$id');

  Future<List<Movimentacao>> listarMovimentacoes() async {
    final dados = await _api.get('/movimentacoes') as List;
    return [for (final item in dados) Movimentacao.fromJson(item as Json)];
  }

  Future<Movimentacao> registrarMovimentacao(MovimentacaoEntrada dados) async =>
      Movimentacao.fromJson(
        await _api.post('/movimentacoes', dados.toJson()) as Json,
      );

  Future<void> removerMovimentacao(int id) => _api.delete('/movimentacoes/$id');
}

/// Situação da API e do banco, para a tela Sistema.
class HealthService {
  const HealthService(this._api);

  final ClienteApi _api;

  Future<ReadinessResponse> buscarReadiness() async {
    // 503 aqui é RESPOSTA, não falha de transporte: a API diz que o banco caiu
    // e manda o corpo explicando.
    final dados = await _api.get('/ready', aceitos: const {200, 503});
    return ReadinessResponse.fromJson(dados as Json);
  }
}
