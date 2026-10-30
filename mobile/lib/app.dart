import 'package:animations/animations.dart';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'core/api/cliente_api.dart';
import 'core/servicos.dart';
import 'core/tema.dart';
import 'models/api.dart';
import 'pages/entrar_page.dart';
import 'pages/importar_page.dart';
import 'pages/insumos_page.dart';
import 'pages/movimentacoes_page.dart';
import 'pages/painel_page.dart';
import 'pages/sistema_page.dart';
import 'services/auth.dart';

const _chaveSolForte = 'modo.sol_forte';

class CampoCertoApp extends StatefulWidget {
  const CampoCertoApp({super.key, required this.api});

  final ClienteApi api;

  @override
  State<CampoCertoApp> createState() => _CampoCertoAppState();
}

class _CampoCertoAppState extends State<CampoCertoApp> {
  final _solForte = ValueNotifier(false);
  // Só pra exibir quem entrou (SistemaPage, por exemplo); não decide a
  // navegação — quem decide é `_mostrarLogin`, abaixo.
  final _usuario = ValueNotifier<Usuario?>(null);
  late final _auth = AuthService(widget.api);
  // Sem autenticação ligada na API (padrão em desenvolvimento), o app abre
  // direto, sem pedir login: a tela só aparece se uma chamada de verdade
  // devolver 401, exatamente como o site faz.
  var _mostrarLogin = false;

  @override
  void initState() {
    super.initState();
    SharedPreferences.getInstance().then((prefs) {
      _solForte.value = prefs.getBool(_chaveSolForte) ?? false;
    });
    _solForte.addListener(_salvarPreferencia);
    widget.api.aoPerderSessao = _aoPerderSessao;
    // Token veio de main.dart (carregado antes do 1º frame); só falta saber
    // quem é, pra mostrar na tela de Sistema.
    if (widget.api.token != null) _confirmarSessao();
  }

  Future<void> _confirmarSessao() async {
    try {
      _usuario.value = await _auth.quemSouEu();
    } catch (_) {
      // Token guardado não vale mais: `aoPerderSessao` cuida de limpar e
      // mostrar o login quando alguma chamada de verdade confirmar o 401.
    }
  }

  Future<void> _aoEntrar(Entrada entrada) async {
    widget.api.token = entrada.token;
    await _auth.salvarToken(entrada.token);
    _usuario.value = entrada.usuario;
    if (mounted) setState(() => _mostrarLogin = false);
  }

  void _aoPerderSessao() {
    widget.api.token = null;
    _usuario.value = null;
    _auth.limparToken();
    if (mounted) setState(() => _mostrarLogin = true);
  }

  Future<void> _salvarPreferencia() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_chaveSolForte, _solForte.value);
  }

  @override
  void dispose() {
    _solForte.removeListener(_salvarPreferencia);
    _solForte.dispose();
    _usuario.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Servicos(
      api: widget.api,
      solForte: _solForte,
      usuario: _usuario,
      child: ValueListenableBuilder(
        valueListenable: _solForte,
        builder: (context, solForte, _) => MaterialApp(
          title: 'CampoCerto',
          theme: temaDoApp(solForte: solForte),
          home: _mostrarLogin
              ? EntrarPage(aoEntrar: _aoEntrar)
              : const Estrutura(),
        ),
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
