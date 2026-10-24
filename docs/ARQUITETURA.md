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
| `app/services/` | Casos de uso: orquestram banco e regra. **Única camada que a rota chama** |
| `app/domain/` | Regras de negócio puras. **Sem I/O, sem banco, sem `datetime.now()`** |
| `app/api/erros.py` | Traduz erro de domínio (`codigo` + `mensagem`) para status HTTP |
| `migrations/` | Alembic. Linhagem única, toda migration com `downgrade` testado |
| `tests/` | Pytest |

Ainda não existe (entra com a primeira análise): `app/analysis/` — análises com Pandas
(consumo, tendência, reposição), que recebem dados e devolvem resultado com **justificativa e
limitações**.

O fluxo é `rota → serviço → (domínio | análise) → ORM`. As setas só apontam para dentro:
`domain` e `analysis` não importam FastAPI nem SQLAlchemy.

### Modelo de dados

| Tabela | Campos | Regras |
|---|---|---|
| `insumo` | nome, categoria?, unidade, estoque_minimo | Nome único **sem diferenciar maiúsculas** (índice em `lower(nome)`) |
| `movimentacao` | insumo_id, tipo (`compra`/`retirada`), quantidade, data, validade?, observacao? | `quantidade > 0`; validade só em compra (CHECK no banco); FK `RESTRICT` |

- **O saldo não é gravado**: é `Σ compras − Σ retiradas`, calculado numa consulta agregada.
  Um saldo gravado ao lado das movimentações poderia divergir delas.
- PKs são **uuid v7** (`uuid.uuid7`, Python 3.14), quantidades `NUMERIC(14,3)`.
- Este modelo veio dos requisitos, não dos arquivos da organização (ainda não recebidos). A
  importação, quando vier, converte para ele.

### Regras de negócio (`app/domain/estoque.py`)

| Regra | Erro |
|---|---|
| Retirada maior que o saldo atual é recusada | `409 ESTOQUE_INSUFICIENTE`, com quantidades na mensagem |
| Remover compra cujo estoque já foi retirado é recusado | `409 ESTOQUE_INSUFICIENTE` |
| Remover insumo com movimentações é recusado (apagaria o histórico) | `409 INSUMO_COM_MOVIMENTACOES` |
| Nome de insumo repetido | `409 INSUMO_DUPLICADO` |

Todo erro de regra tem corpo `{"codigo", "mensagem"}`. O front mostra a `mensagem` como veio;
validação de formato (Pydantic) devolve `422`.

**Limitação conhecida:** a checagem de saldo e a gravação não são atômicas — duas retiradas
simultâneas do mesmo insumo poderiam passar juntas. Aceitável com um usuário; se houver uso
concorrente, travar a linha do insumo (`SELECT ... FOR UPDATE`) no serviço.

### Endpoints atuais

| Rota | O que faz |
|---|---|
| `GET /api/v1/health` | Liveness — o processo está no ar. Não toca o banco |
| `GET /api/v1/ready` | Readiness — `200` com o banco respondendo, `503` sem ele |
| `GET/POST /api/v1/insumos` | Lista (com `saldo_atual`, ordem alfabética) / cadastra |
| `GET/PUT/DELETE /api/v1/insumos/{id}` | Detalhe / edita / remove (só sem movimentações) |
| `GET/POST /api/v1/movimentacoes` | Lista (mais recentes primeiro; `?insumo_id=` filtra) / registra |
| `DELETE /api/v1/movimentacoes/{id}` | Remove (recalcula o saldo) |
| `GET /api/v1/docs` | Swagger UI (desligado em `production`) |
| `GET /api/v1/openapi.json` | Schema OpenAPI (desligado em `production`) |

## 3. Frontend (`frontend/`)

| Caminho | Responsabilidade |
|---|---|
| `src/main.ts` | Instala Pinia e Router, importa o CSS |
| `src/router/` | Rotas. Páginas além do Painel entram por `import()` dinâmico. **O menu é derivado das rotas** (`meta.menu`): registrar uma tela é um lugar só |
| `src/layouts/` | `AppLayout`: menu lateral fixo no desktop, gaveta no celular, resumo de status |
| `src/pages/` | Uma página por rota: Painel, Insumos, Movimentações, Importar dados, Sistema |
| `src/components/` | Reutilizáveis. Os formulários (`FormularioInsumo`, `FormularioMovimentacao`) salvam pela store; os demais (`JanelaModal`, `ConfirmarRemocao`, `AvisoDeErro`, `CabecalhoDePagina`, `EstadoVazio`, `IconeSvg`, `IndicadorDeStatus`) só exibem |
| `src/formatos.ts` | Formatação pt-BR de quantidade e data (só apresentação) |
| `src/stores/` | Pinia — estado compartilhado e as ações que chamam os serviços |
| `src/services/http.ts` | **Cliente HTTP único** (Axios). Normaliza erro em `ApiError` |
| `src/services/*.ts` | Uma função por endpoint |
| `src/types/` | Tipos TypeScript dos contratos da API |
| `src/styles/main.css` | Tailwind v4, tokens da marca (`@theme`) e classes `botao-*`, `campo`, `rotulo` |
| `tests/unit/` | Vitest + Vue Test Utils |

Regras: componente `.vue` **não chama axios** (passa por store → `services/`) e **não decide**
regra de negócio — mostra o que a API calculou, inclusive o saldo e as mensagens de erro.

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

1. **Formato dos dados da organização** — não presumido. O cadastro manual usa um modelo próprio;
   a importação vai converter os arquivos para ele.
2. **Autenticação** — o desafio não exige; decidir se a demonstração é monousuário.
3. **Geração de tipos TS a partir do OpenAPI** (`openapi-typescript`) quando houver mais de um
   recurso.
4. **Pandas e Apache ECharts** entram com a primeira análise e o primeiro gráfico — não foram
   instalados antes de ter uso.
