import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

/// A câmera, lendo código de barras ou QR code. Fecha sozinha devolvendo o
/// primeiro valor lido (`Navigator.pop`); `null` se a pessoa voltar sem ler.
class LeitorDeCodigoDeBarrasPage extends StatefulWidget {
  const LeitorDeCodigoDeBarrasPage({super.key});

  @override
  State<LeitorDeCodigoDeBarrasPage> createState() =>
      _LeitorDeCodigoDeBarrasPageState();
}

class _LeitorDeCodigoDeBarrasPageState
    extends State<LeitorDeCodigoDeBarrasPage> {
  // Evita devolver dois códigos: a câmera dispara onDetect várias vezes
  // enquanto o código continua no quadro, antes da tela fechar.
  var _lido = false;

  void _aoDetectar(BarcodeCapture captura) {
    if (_lido || captura.barcodes.isEmpty) return;
    final codigo = captura.barcodes.first.rawValue;
    if (codigo == null) return;
    _lido = true;
    Navigator.pop(context, codigo);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Ler código de barras')),
      body: MobileScanner(onDetect: _aoDetectar),
    );
  }
}
