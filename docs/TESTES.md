# Testes

## Backend — Pytest (`backend/tests/`)

A suíte usa **SQLite em memória** (`DATABASE_URL=sqlite://`, definido em `tests/conftest.py`),
então não precisa de Docker nem de PostgreSQL. A fixture `db` cria as tabelas dos modelos num
banco novo por teste, e `client` usa esse banco no lugar do `get_db`.

| Arquivo | Cobre |
|---|---|
| `test_health.py` | `/health` responde; `/ready` dá 200 com banco e **503** quando o banco falha |
| `test_config.py` | `ENVIRONMENT` obrigatório e restrito; `/docs` ligado fora de produção e desligado em produção |
| `test_estoque.py` | Cadastro de insumo (nome repetido = `409`), estoque e análise calculados das movimentações, movimentação inválida (`422`), alteração, listagem e remoção |
| `test_analises.py` | `POST /analises`: resposta com alertas, reposição e limitações; `422` para período invertido e retirada negativa |
| `test_motor_de_analise.py` | Cada alerta do motor (mínimo, falta, vencimento, excesso, baixa movimentação, consumo incomum), a reposição estimada com as contas à mão, e as limitações quando falta histórico ou cadastro |

```bash
make test-backend                 # no container
cd backend && uv run pytest       # no host (exige uv)
uv run pytest tests/test_health.py -k ready -v
```

**Regras:** regra de domínio e análise são testadas sem banco, com dados construídos no próprio
teste. Nada de dado real do desafio em fixture — sintético, sempre. Teste não acessa a internet.

## Frontend — Vitest (`frontend/tests/unit/`)

Ambiente `jsdom`, configurado em `vite.config.ts`. Os serviços HTTP são substituídos por
`vi.mock`, sem rede.

| Arquivo | Cobre |
|---|---|
| `navegacao.spec.ts` | Cada rota renderiza a sua página (inclusive 404); menu lista as telas na ordem; gaveta abre e fecha ao navegar; resumo de status no menu |
| `statusSistema.spec.ts` | Store: API e banco ok; banco indisponível; API fora do ar não afirma nada sobre o banco; getter `situacao` |
| `IndicadorDeStatus.spec.ts` | Componente mostra o texto de cada estado |

```bash
make test-frontend                # no container
cd frontend && npm test           # no host (exige Node 24)
```

## Integração real (API ↔ PostgreSQL)

Com o stack no ar (`make up`):

```bash
make check-db
```

Confere `GET /api/v1/ready` → `{"status":"pronto","database":"ok"}` e lê a revisão aplicada na
tabela `alembic_version` do PostgreSQL (deve ser `0001`).

## Lint e tipos

```bash
make lint      # ruff check + ruff format --check + vue-tsc + eslint
make verify    # lint + todos os testes — rodar antes de commitar
```
