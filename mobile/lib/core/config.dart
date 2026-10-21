/// Configuração do app, decidida na hora do build.
///
/// Diferente do site, o app não vive na mesma origem da API: o endereço precisa
/// ser informado. Troque com `--dart-define`:
///
///     flutter run --dart-define=API_URL=http://192.168.0.10:8000/api/v1
library;

/// Endereço base da API v1, sem barra no fim.
///
/// O padrão `10.0.2.2` é como o emulador do Android enxerga o `localhost` do
/// computador. No simulador do iOS use `http://127.0.0.1:8000/api/v1`; num
/// celular de verdade, o IP do computador na rede local.
const String urlDaApi = String.fromEnvironment(
  'API_URL',
  defaultValue: 'http://10.0.2.2:8000/api/v1',
);
