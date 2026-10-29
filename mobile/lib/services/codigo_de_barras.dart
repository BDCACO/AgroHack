import '../models/api.dart';

/// O insumo já ensinado com esse código de barras, ou nulo se nenhum tiver.
Insumo? insumoPeloCodigoDeBarras(List<Insumo> insumos, String codigo) {
  for (final insumo in insumos) {
    if (insumo.codigoDeBarras == codigo) return insumo;
  }
  return null;
}
