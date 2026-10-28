import type {
  Fornecedor,
  FornecedorCadastro,
  FornecedorDetalhe,
  Pedido,
  PedidoEntrada,
  Recebimento,
  ResultadoDoRecebimento,
  SugestaoDePedido,
} from '@/types/api'

import { http } from './http'

export async function listarFornecedores(): Promise<Fornecedor[]> {
  const { data } = await http.get<Fornecedor[]>('/fornecedores')
  return data
}

export async function buscarFornecedor(id: number): Promise<FornecedorDetalhe> {
  const { data } = await http.get<FornecedorDetalhe>(`/fornecedores/${id}`)
  return data
}

export async function criarFornecedor(dados: FornecedorCadastro): Promise<Fornecedor> {
  const { data } = await http.post<Fornecedor>('/fornecedores', dados)
  return data
}

export async function atualizarFornecedor(id: number, dados: FornecedorCadastro): Promise<Fornecedor> {
  const { data } = await http.put<Fornecedor>(`/fornecedores/${id}`, dados)
  return data
}

export async function removerFornecedor(id: number): Promise<void> {
  await http.delete(`/fornecedores/${id}`)
}

/** Os mais recentes primeiro. A tela separa por situação. */
export async function listarPedidos(): Promise<Pedido[]> {
  const { data } = await http.get<Pedido[]>('/pedidos')
  return data
}

/** As reposições dos próximos `dias`, agrupadas pela revenda da última compra. */
export async function sugerirPedido(dias = 7): Promise<SugestaoDePedido> {
  const { data } = await http.get<SugestaoDePedido>('/pedidos/sugestao', { params: { dias } })
  return data
}

export async function criarPedido(dados: PedidoEntrada): Promise<Pedido> {
  const { data } = await http.post<Pedido>('/pedidos', dados)
  return data
}

/** Só o pedido aberto, antes de chegar qualquer coisa. */
export async function atualizarPedido(id: number, dados: PedidoEntrada): Promise<Pedido> {
  const { data } = await http.put<Pedido>(`/pedidos/${id}`, dados)
  return data
}

export async function cancelarPedido(id: number): Promise<Pedido> {
  const { data } = await http.post<Pedido>(`/pedidos/${id}/cancelar`)
  return data
}

export async function receberPedido(id: number, dados: Recebimento): Promise<ResultadoDoRecebimento> {
  const { data } = await http.post<ResultadoDoRecebimento>(`/pedidos/${id}/receber`, dados)
  return data
}
