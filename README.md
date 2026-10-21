# CampoCerto

Plataforma de gestão inteligente de insumos rurais, feita para o **AGROHACK 2026/2, IFRO Campus Ariquemes**.

Transforma registros de compras, retiradas e estoque em informação para decisão: estoque abaixo
do mínimo, risco de falta, vencimento próximo, excesso, baixa movimentação, consumo incomum e
reposição estimada, sempre com justificativa e limitações explícitas.

> **Estado atual:** cadastro de insumos e lançamento de entradas e saídas pela tela ou por
> planilha do Excel ou CSV (com planilha modelo formatada e prévia antes de gravar); o Painel
> mostra os alertas do motor de análise com a justificativa de cada um, a reposição estimada
> (com lista de compras para o WhatsApp) e as limitações. Cada insumo tem uma página com o
> gráfico do estoque e a projeção de quando acaba. Tudo sai num relatório em Excel, que também
> é a cópia de segurança das movimentações.

## Stack

| Camada | Tecnologias |
|---|---|
| Frontend | Vue 3, TypeScript, Vite, Vue Router, Pinia, Tailwind CSS v4, Axios, Apache ECharts, Plus Jakarta Sans |
| Backend | Python 3.14, FastAPI, Pydantic, SQLAlchemy 2, Alembic, openpyxl, Pytest |
| App | Flutter 3.47 (Dart 3.13), Android e iOS, pacote `http` |
| Banco | PostgreSQL 18 |
| Infra | Docker, Docker Compose |

## Pré-requisitos

- Docker com Docker Compose v2.
- Opcional, para rodar fora do container: [uv](https://docs.astral.sh/uv/) (backend) e Node 24
  (frontend).

## Como subir

```bash
cp .env.example .env        # e troque POSTGRES_PASSWORD (só letras e números)
make up                     # banco + API + frontend
```

| Endereço | O quê |
|---|---|
| http://localhost:5173 | Aplicação |
| http://localhost:8000/api/v1/docs | Documentação interativa da API (Swagger) |
| http://localhost:8000/api/v1/health | Liveness da API |
| http://localhost:8000/api/v1/ready | API + banco |

A página inicial mostra a situação da API e do banco: é a verificação visual de que as três
partes estão conectadas.

Sem `make`? Os alvos são atalhos de `docker compose`: `docker compose up --build`.

## Demonstração

Sem dados reais à mão, `make demo` (com o stack no ar) cria uma fazenda **fictícia** com 6 meses
de movimentações, pensada para acender cada tipo de alerta, mais um insumo saudável para
contraste. As datas são relativas ao dia da carga: rode no dia da apresentação. A tela avisa que
são dados de demonstração, e `make demo-limpar` apaga só eles, preservando o que foi cadastrado.

Para mostrar a importação, a tela **Importar dados** oferece a planilha modelo do Excel, gerada
na hora com os insumos cadastrados; como preencher está em
[`docs/IMPORTACAO.md`](docs/IMPORTACAO.md).

## Comandos

```bash
make help       # lista tudo
make up         # sobe os serviços
make down       # derruba (os dados do banco ficam no volume)
make logs       # logs
make migrate    # alembic upgrade head
make demo       # carrega a fazenda de demonstração (fictícia, datas relativas a hoje)
make demo-limpar  # apaga só os dados de demonstração
make test       # pytest + vitest
make lint       # ruff + vue-tsc + eslint
make check-db   # confere API ↔ PostgreSQL com o stack no ar
make verify     # lint + testes, antes de commitar
```

### Rodando fora do Docker

```bash
# Backend (precisa de um PostgreSQL; o do compose fica em 127.0.0.1:5433)
cd backend
uv sync
export ENVIRONMENT=development
export DATABASE_URL=postgresql+psycopg://campocerto:SENHA@127.0.0.1:5433/campocerto
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# Frontend (o proxy aponta para localhost:8000 por padrão)
cd frontend
npm install
npm run dev
```

## App para celular

Além do site, há um app nativo para Android e iOS em Flutter, em [`mobile/`](mobile/README.md).
Usa a mesma API; o endereço dela vem do build:

```bash
cd mobile
flutter run                                                  # emulador do Android
flutter run --dart-define=API_URL=http://192.168.0.10:8000/api/v1   # celular na rede
```

Hoje tem Painel, Insumos, Movimentações e Sistema; a importação de planilha ainda é só pelo site.

## Variáveis de ambiente

Todas em `.env` na raiz; o modelo comentado está em [`.env.example`](.env.example).

| Variável | Obrigatória | Uso |
|---|---|---|
| `ENVIRONMENT` | sim | `development`, `test` ou `production`. Outro valor impede a API de subir |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | sim | Banco; o compose monta o `DATABASE_URL` da API com elas |
| `DB_PORT`, `API_PORT`, `WEB_PORT` | não | Portas no host (5433, 8000, 5173) |
| `LOG_LEVEL` | não | Nível de log da API (`INFO`) |

## Documentação

- [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md): estrutura, camadas, decisões e o que foi
  herdado do ArkoHub.
- [`docs/IMPORTACAO.md`](docs/IMPORTACAO.md): como preencher e importar a planilha de
  movimentações (Excel ou CSV), formatos aceitos e erros comuns.
- [`docs/TESTES.md`](docs/TESTES.md): o que cada suíte cobre e como rodar.
- [`docs/APRESENTACAO.md`](docs/APRESENTACAO.md): roteiro da demonstração com a fazenda fictícia.

## Estrutura

```
CampoCerto/
├── compose.yaml · Makefile · .env.example
├── backend/
│   ├── app/
│   │   ├── main.py              # create_app()
│   │   ├── core/                # config, database
│   │   ├── api/                 # router + routes/
│   │   ├── domain/              # regras de estoque puras (sem I/O)
│   │   ├── analysis/            # motor de análise: consumo, alertas, reposição
│   │   ├── schemas/             # Pydantic
│   │   └── models/              # SQLAlchemy
│   ├── migrations/              # Alembic
│   ├── tests/
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── router/ layouts/ pages/ components/
│   │   ├── stores/              # Pinia
│   │   ├── services/            # Axios (cliente único em http.ts)
│   │   ├── types/
│   │   └── styles/              # Tailwind
│   └── tests/unit/
├── mobile/                  # app Flutter (Android e iOS), ver mobile/README.md
│   ├── lib/                 # core/ models/ services/ pages/ widgets/
│   └── test/
└── docs/
```
