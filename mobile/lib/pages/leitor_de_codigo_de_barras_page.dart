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
      appBar: AppBar(title: const Text('Ler código de barras ou QR Code')),
      body: Stack(
        fit: StackFit.expand,
        children: [
          MobileScanner(onDetect: _aoDetectar),
          const _MiraDeLeitura(),
        ],
      ),
    );
  }
}

/// Moldura sobre a câmera: uma janela recortada, com cantos em L, que serve
/// tanto para mirar um QR code (quadrado) quanto um código de barras (mais
/// largo que alto) sem precisar de duas telas diferentes.
class _MiraDeLeitura extends StatelessWidget {
  const _MiraDeLeitura();

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, restricoes) {
        final janela = Rect.fromCenter(
          center: Offset(restricoes.maxWidth / 2, restricoes.maxHeight / 2),
          width: restricoes.maxWidth * 0.8,
          height: restricoes.maxWidth * 0.8 * 0.55,
        );
        return Stack(
          children: [
            Positioned.fill(child: CustomPaint(painter: _PintorDaMira(janela))),
            Positioned(
              left: janela.left,
              top: janela.bottom + 16,
              width: janela.width,
              child: const Text(
                'Aponte para um código de barras ou QR Code',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.white, fontSize: 14),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _PintorDaMira extends CustomPainter {
  _PintorDaMira(this.janela);

  final Rect janela;
  static const _raioDaJanela = Radius.circular(16);
  static const _tamanhoDoCanto = 24.0;

  @override
  void paint(Canvas canvas, Size size) {
    final fundo = Path()..addRect(Offset.zero & size);
    final recorte = Path()
      ..addRRect(RRect.fromRectAndRadius(janela, _raioDaJanela));
    canvas.drawPath(
      Path.combine(PathOperation.difference, fundo, recorte),
      Paint()..color = const Color(0x99000000),
    );

    final cantoPaint = Paint()
      ..color = Colors.white
      ..strokeWidth = 4
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    void canto(Offset ponta, Offset h, Offset v) {
      canvas
        ..drawLine(ponta, ponta + h, cantoPaint)
        ..drawLine(ponta, ponta + v, cantoPaint);
    }

    canto(janela.topLeft, Offset(_tamanhoDoCanto, 0), Offset(0, _tamanhoDoCanto));
    canto(janela.topRight, Offset(-_tamanhoDoCanto, 0), Offset(0, _tamanhoDoCanto));
    canto(janela.bottomLeft, Offset(_tamanhoDoCanto, 0), Offset(0, -_tamanhoDoCanto));
    canto(
      janela.bottomRight,
      Offset(-_tamanhoDoCanto, 0),
      Offset(0, -_tamanhoDoCanto),
    );
  }

  @override
  bool shouldRepaint(covariant _PintorDaMira oldDelegate) =>
      oldDelegate.janela != janela;
}
