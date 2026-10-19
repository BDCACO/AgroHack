# CampoCerto

Plataforma de gestão inteligente de insumos rurais — **AGROHACK 2026/2, IFRO Campus Ariquemes**.

Transforma registros de compras, retiradas e estoque em informação para decisão: estoque abaixo
do mínimo, risco de falta, vencimento próximo, excesso, baixa movimentação, consumo incomum e
reposição estimada — sempre com justificativa e limitações explícitas.

> **Estado atual:** frontend, API e banco sobem e conversam entre si. O motor de análise
> (`backend/app/domain` + `backend/app/analysis`) está pronto, testado e exposto em
> `POST /api/v1/analises` (dados no corpo, sem banco). A modelagem e a importação esperam o
> formato dos dados da organização.

## Stack

| Camada | Tecnologias |
|---|---|
| Frontend | Vue 3, TypeScript, Vite, Vue Router, Pinia, Tailwind CSS v4, Axios |
| Backend | Python 3.14, FastAPI, Pydantic, SQLAlchemy 2, Alembic, Pytest |
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

A página inicial mostra a situação da API e do banco — é a verificação visual de que as três
partes estão conectadas.

Sem `make`? Os alvos são atalhos de `docker compose`: `docker compose up --build`.

## Comandos

```bash
make help       # lista tudo
make up         # sobe os serviços
make down       # derruba (os dados do banco ficam no volume)
make logs       # logs
make migrate    # alembic upgrade head
make test       # pytest + vitest
make lint       # ruff + vue-tsc + eslint
make check-db   # confere API ↔ PostgreSQL com o stack no ar
make verify     # lint + testes — antes de commitar
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

## Variáveis de ambiente

Todas em `.env` na raiz — modelo comentado em [`.env.example`](.env.example).

| Variável | Obrigatória | Uso |
|---|---|---|
| `ENVIRONMENT` | sim | `development`, `test` ou `production`. Outro valor impede a API de subir |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | sim | Banco; o compose monta o `DATABASE_URL` da API com elas |
| `DB_PORT`, `API_PORT`, `WEB_PORT` | não | Portas no host (5433, 8000, 5173) |
| `LOG_LEVEL` | não | Nível de log da API (`INFO`) |

## Documentação

- [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) — estrutura, camadas, decisões e o que foi
  herdado do ArkoHub.
- [`docs/TESTES.md`](docs/TESTES.md) — o que cada suíte cobre e como rodar.

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
└── docs/
```
