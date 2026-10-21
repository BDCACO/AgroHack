# CampoCerto para Android e iOS

App nativo em Flutter. Fala com a mesma API do site (`backend/`); toda regra de negócio e
análise continua lá, o app só exibe e coleta.

## Pré-requisitos

- Flutter 3.47.7 (Dart 3.13.5), a versão com que o projeto foi gerado e que a CI usa.
- Para rodar num aparelho: Android Studio com um emulador, ou Xcode (só no Mac) para o iOS.
- A API no ar (`make up` na raiz, ou o backend rodando fora do Docker).

## Rodando

```bash
cd mobile
flutter pub get
flutter run                     # emulador do Android: a API padrão é http://10.0.2.2:8000/api/v1
```

O app não vive na mesma origem da API como o site, então o endereço vem do build:

| Onde o app roda | `API_URL` |
|---|---|
| Emulador do Android | `http://10.0.2.2:8000/api/v1` (padrão) |
| Simulador do iOS | `http://127.0.0.1:8000/api/v1` |
| Celular de verdade, na mesma rede | `http://<IP do computador>:8000/api/v1` |

```bash
flutter run --dart-define=API_URL=http://192.168.0.10:8000/api/v1
```

Num celular de verdade, a API precisa escutar na rede (`uvicorn ... --host 0.0.0.0`) e o
firewall do computador precisa liberar a porta 8000. O `http://` sem TLS só é aceito no build
de debug do Android e, no iOS, só na rede local; o release exige `https://`.

## Testes

```bash
flutter analyze
flutter test        # modelos, cliente da API e as telas contra uma API falsa
```

## Estrutura

```
lib/
├── main.dart · app.dart     # entrada, tema e a barra de navegação com as cinco telas
├── core/
│   ├── config.dart          # API_URL (--dart-define)
│   ├── api/cliente_api.dart # cliente HTTP único e ApiError
│   ├── servicos.dart        # serviços ao alcance das telas (Servicos.of)
│   └── tema.dart            # cores da marca, rótulos de alerta e de gravidade
├── models/api.dart          # espelho dos schemas da API (como o types/api.ts do site)
├── services/estoque.dart    # rotas de insumos, movimentações e /ready
├── pages/                   # Painel, Insumos, Movimentações, Importar, Sistema
└── widgets/                 # CarregarDados (carregando, erro, puxar para atualizar), formatação
```
