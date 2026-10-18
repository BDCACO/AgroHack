# Arquitetura do CampoCerto

Plataforma de gestão inteligente de insumos rurais (AGROHACK 2026/2 — IFRO Campus Ariquemes).
Transforma registros de compras, retiradas e estoque em alertas justificados para o produtor.

Este documento registra **o que existe hoje** e **as decisões tomadas**, incluindo o que foi
herdado do ArkoHub (projeto de referência) e o que foi deliberadamente deixado de fora.

## 1. Visão geral

```
navegador ──► Vite (:5173) ──/api──► FastAPI (:8000) ──► PostgreSQL
              Vue 3 + Pinia           SQLAlchemy 2 + Alembic
```

- Front e API vivem na **mesma origem**: o navegador fala só com o Vite, que repassa `/api`.
  Não há CORS para configurar; em produção um reverse proxy faz o mesmo papel.
- O frontend **exibe e coleta**; regra de negócio e análise ficam no backend.

## 2. Backend (`backend/`)

| Caminho | Responsabilidade |
|---|---|
| `app/main.py` | Fábrica `create_app(settings)` — testes criam a sua com configuração própria |
| `app/core/config.py` | `Settings` (pydantic-settings). Única fonte de variáveis de ambiente |
| `app/core/database.py` | Engine, sessão e a dependência `get_db` |
| `app/api/router.py` | Agrega as rotas da v1 (`/api/v1`) |
| `app/api/routes/` | Rotas HTTP — finas: validam entrada, chamam serviço, devolvem schema |
| `app/schemas/` | Modelos Pydantic de entrada/saída da API |
| `app/models/` | Modelos ORM (SQLAlchemy). Todo modelo novo é importado em `models/__init__.py` |
| `migrations/` | Alembic. Linhagem única, toda migration com `downgrade` |
| `tests/` | Pytest |

### Camadas previstas (criadas quando houver código para elas)

Para não manter diretórios vazios, estas pastas **ainda não existem**. Entram junto com a
primeira funcionalidade que as usar:

| Caminho | Responsabilidade | Regra |
|---|---|---|
| `app/services/` | Casos de uso: orquestram repositório, regra e análise | Única camada que a rota chama |
| `app/domain/` | Regras de negócio puras (limiar de estoque mínimo, vencimento...) | **Sem I/O, sem banco, sem `datetime.now()`** — a data de referência entra como parâmetro |
| `app/analysis/` | Análises com Pandas (consumo, tendência, estimativa de reposição) | Recebe DataFrame/listas, devolve resultado + **justificativa e limitações** |

O fluxo esperado é `rota → serviço → (domínio | análise) → repositório/ORM`. As setas só
apontam para dentro: `domain` e `analysis` não importam FastAPI nem SQLAlchemy.

### Endpoints atuais

| Rota | O que faz |
|---|---|
| `GET /api/v1/health` | Liveness — o processo está no ar. Não toca o banco |
| `GET /api/v1/ready` | Readiness — `200` com o banco respondendo, `503` sem ele |
| `GET /api/v1/docs` | Swagger UI (desligado em `production`) |
| `GET /api/v1/openapi.json` | Schema OpenAPI (desligado em `production`) |

## 3. Frontend (`frontend/`)

| Caminho | Responsabilidade |
|---|---|
| `src/main.ts` | Instala Pinia e Router, importa o CSS |
| `src/router/` | Rotas. Páginas além da inicial entram por `import()` dinâmico |
| `src/layouts/` | Moldura das telas (cabeçalho responsivo, rodapé) |
| `src/pages/` | Uma página por rota |
| `src/components/` | Componentes reutilizáveis, sem chamada à API |
| `src/stores/` | Pinia — estado compartilhado e as ações que chamam os serviços |
| `src/services/http.ts` | **Cliente HTTP único** (Axios). Normaliza erro em `ApiError` |
| `src/services/*.ts` | Uma função por endpoint |
| `src/types/` | Tipos TypeScript dos contratos da API |
| `src/styles/main.css` | Tailwind v4 + tokens da marca (`@theme`) |
| `tests/unit/` | Vitest + Vue Test Utils |

Regras: componente `.vue` **não chama axios** (passa por `services/`) e **não decide** regra de
negócio — mostra o que a API calculou.

## 4. Infraestrutura

`compose.yaml` na raiz sobe `db` (PostgreSQL 18), `api` (imagem `backend/Dockerfile`, alvo `dev`,
com `--reload`) e `web` (Node 24 rodando o Vite). A API aplica `alembic upgrade head` ao subir
(`backend/docker/entrypoint.sh`); a espera pelo banco é o `healthcheck` do compose.

Configuração por `.env` na raiz (modelo em `.env.example`). Variáveis obrigatórias sem default:
`ENVIRONMENT` e `DATABASE_URL` (montada pelo compose a partir de `POSTGRES_*`).

## 5. Herdado do ArkoHub × decidido diferente

O ArkoHub é um SaaS multi-tenant de ferramentas para escritórios (FastAPI + Vue 3/Vuetify +
PostgreSQL com RLS + MinIO + Redis + worker). O CampoCerto aproveita os **padrões**, não as
tecnologias que não se aplicam.

**Aproveitado**

- Monorepo `backend/` + `frontend/` com responsabilidades separadas; FastAPI como fonte da verdade
  do contrato.
- `Settings` com pydantic-settings, validado no boot, **`ENVIRONMENT` obrigatório e restrito** a
  valores conhecidos (fail-closed) e `/docs` desligado em produção.
- Separação **liveness (`/health`) × readiness (`/ready`)**.
- Front e API na mesma origem via proxy do Vite — sem CORS.
- Cliente HTTP único no front; nenhuma chamada HTTP crua espalhada.
- Rotas com `import()` dinâmico.
- `uv` + `pyproject.toml` com faixas de versão com teto; `ruff`; `pytest`.
- Imagem Docker multi-stage, usuário não-root, migrations no entrypoint.
- `Makefile` com `help`, e testes/lint rodando **dentro do container**.
- Domínio sem I/O e sem relógio implícito; sem `utils.py`/`helpers.ts` ("código mora ao lado
  do que serve").
- Código, comentários e nomes em português; comentário explica o **porquê**.

**Deixado de fora (e por quê)**

| ArkoHub | CampoCerto | Motivo |
|---|---|---|
| Multi-tenant com RLS, roles `hub_owner`/`hub_api` | Banco simples, uma role | Não há múltiplos clientes isolados no escopo do desafio |
| SQLAlchemy **async** + asyncpg/psycopg | SQLAlchemy **síncrono** + psycopg 3 | Análise com Pandas é síncrona e CPU-bound; rotas `def` rodam em threadpool |
| Alembic sem autogenerate (`target_metadata=None`) | Autogenerate ligado, migration **revisada** | Lá o motivo era RLS invisível ao autogenerate; aqui não existe |
| Vuetify | Tailwind CSS v4 | Stack definida para o projeto |
| openapi-fetch + TanStack Query | Axios + Pinia | Stack definida para o projeto |
| Tipos TS gerados do OpenAPI | Escritos à mão (por ora) | Dois endpoints; geração entra quando a API crescer |
| Dois stacks compose + rede `edge` | Um compose só | Sem serviços internos (MinIO, Redis, worker) a isolar |
| MinIO, Redis, worker, ClamAV, rate-limit, auth com sessão | — | Nenhum requisito do CampoCerto pede, por ora |
| mypy strict, import-linter, dependency-cruiser, cobertura 90% | ruff + vue-tsc + eslint | Proporcional ao tamanho; os gates entram se as regras de camada começarem a ser violadas |

## 6. Próximas decisões (pendentes)

1. **Formato dos dados da organização** — não presumido. A modelagem (`models/`) e a importação
   dependem dele.
2. **Autenticação** — o desafio não exige; decidir se a demonstração é monousuário.
3. **Geração de tipos TS a partir do OpenAPI** (`openapi-typescript`) quando houver mais de um
   recurso.
4. **Pandas e Apache ECharts** entram com a primeira análise e o primeiro gráfico — não foram
   instalados antes de ter uso.
