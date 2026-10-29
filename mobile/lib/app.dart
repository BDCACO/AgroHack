import 'package:animations/animations.dart';
import 'package:flutter/material.dart';

import 'core/api/cliente_api.dart';
import 'core/servicos.dart';
import 'core/tema.dart';
import 'pages/importar_page.dart';
import 'pages/insumos_page.dart';
import 'pages/movimentacoes_page.dart';
import 'pages/painel_page.dart';
import 'pages/sistema_page.dart';

class CampoCertoApp extends StatelessWidget {
  const CampoCertoApp({super.key, required this.api});

  final ClienteApi api;

  @override
  Widget build(BuildContext context) {
    return Servicos(
      api: api,
      child: MaterialApp(
        title: 'CampoCerto',
        theme: temaDoApp(),
        home: const Estrutura(),
      ),
    );
  }
}

class _Tela {
  const _Tela(this.titulo, this.icone, this.pagina);

  final String titulo;
  final IconData icone;
  final Widget pagina;
}

// As telas da barra de baixo, na ordem do menu do site.
const _telas = [
  _Tela('Painel', Icons.dashboard_outlined, PainelPage()),
  _Tela('Insumos', Icons.inventory_2_outlined, InsumosPage()),
  _Tela('Movimentações', Icons.swap_vert, MovimentacoesPage()),
  _Tela('Importar', Icons.upload_file_outlined, ImportarPage()),
  _Tela('Sistema', Icons.monitor_heart_outlined, SistemaPage()),
];

/// A barra de navegação embaixo, ao alcance do polegar, como na versão para
/// celular do site.
class Estrutura extends StatefulWidget {
  const Estrutura({super.key});

  @override
  State<Estrutura> createState() => _EstruturaState();
}

class _EstruturaState extends State<Estrutura> {
  var _atual = 0;
  var _indoPraFrente = true;

  @override
  Widget build(BuildContext context) {
    final tela = _telas[_atual];
    // "Reduzir movimento" do sistema: troca instantânea, sem transição.
    final reduzido = MediaQuery.of(context).disableAnimations;
    return Scaffold(
      appBar: AppBar(title: Text(tela.titulo)),
      // Cada tela busca seus dados ao aparecer, e de novo ao voltar para ela.
      // Eixo compartilhado horizontal: a aba mais à direita entra pela
      // direita, a mais à esquerda pela esquerda — não é só um fade.
      body: PageTransitionSwitcher(
        duration: reduzido ? Duration.zero : const Duration(milliseconds: 280),
        reverse: !_indoPraFrente,
        transitionBuilder: (child, animation, animacaoSecundaria) =>
            SharedAxisTransition(
              animation: animation,
              secondaryAnimation: animacaoSecundaria,
              transitionType: SharedAxisTransitionType.horizontal,
              child: child,
            ),
        child: KeyedSubtree(key: ValueKey(_atual), child: tela.pagina),
      ),
      bottomNavigationBar: _BarraInferior(
        selectedIndex: _atual,
        onDestinationSelected: (i) => setState(() {
          _indoPraFrente = i >= _atual;
          _atual = i;
        }),
      ),
    );
  }
}

/// A NavigationBar, só que o ícone encolhe ao toque — como o
/// `group-active:scale-90` da barra de baixo do site — em vez de só o ripple
/// do Material.
class _BarraInferior extends StatelessWidget {
  const _BarraInferior({
    required this.selectedIndex,
    required this.onDestinationSelected,
  });

  final int selectedIndex;
  final ValueChanged<int> onDestinationSelected;

  @override
  Widget build(BuildContext context) {
    return NavigationBar(
      selectedIndex: selectedIndex,
      onDestinationSelected: onDestinationSelected,
      destinations: [
        for (final t in _telas)
          NavigationDestination(
            icon: _IconeComToque(icone: t.icone),
            label: t.titulo,
          ),
      ],
    );
  }
}

/// Encolhe o ícone enquanto o dedo toca, como o `group-active:scale-90` do
/// site — puramente visual, não intercepta o toque que seleciona a aba.
class _IconeComToque extends StatefulWidget {
  const _IconeComToque({required this.icone});

  final IconData icone;

  @override
  State<_IconeComToque> createState() => _IconeComToqueState();
}

class _IconeComToqueState extends State<_IconeComToque> {
  var _pressionado = false;

  void _definir(bool valor) {
    if (_pressionado != valor) setState(() => _pressionado = valor);
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.translucent,
      onTapDown: (_) => _definir(true),
      onTapUp: (_) => _definir(false),
      onTapCancel: () => _definir(false),
      child: AnimatedScale(
        scale: _pressionado ? 0.9 : 1,
        duration: const Duration(milliseconds: 100),
        curve: Curves.easeOut,
        child: Icon(widget.icone),
      ),
    );
  }
}
