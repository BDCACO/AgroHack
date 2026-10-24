# Testes

## Backend — Pytest (`backend/tests/`)

Por padrão a suíte usa **SQLite em memória** (`tests/conftest.py`), então não precisa de Docker.
Com `TEST_DATABASE_URL` a **mesma suíte** roda contra um PostgreSQL real — `make test-db` faz
isso no banco `campocerto_teste` (separado: as tabelas são criadas e apagadas a cada teste).

| Arquivo | Cobre |
|---|---|
| `test_health.py` | `/health` responde; `/ready` dá 200 com banco e **503** quando o banco falha |
| `test_config.py` | `ENVIRONMENT` obrigatório e restrito; `/docs` ligado fora de produção e desligado em produção |
| `test_dominio_estoque.py` | Regras de saldo puras: retirada além do saldo, remoção de compra consumida, mensagem formatada |
| `test_insumos.py` | CRUD; nome aparado, único sem diferenciar maiúsculas; mínimo negativo; 404; remoção bloqueada com histórico |
| `test_movimentacoes.py` | Saldo após compra/retirada; 409 por estoque insuficiente; validade só em compra; filtro e ordem; remoções |

```bash
make test-backend                 # no container, SQLite
make test-db                      # no container, PostgreSQL real (exige make up)
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
| `InsumosPage.spec.ts` | Lista com saldo formatado; estado vazio; cadastro (payload e recarga); erro da API no formulário; remoção recusada |
| `FormularioMovimentacao.spec.ts` | Saldo e unidade do insumo; validade só em compra (e não enviada em retirada); explicação de estoque insuficiente |
| `http.spec.ts` | `mensagemDeErro`: mensagem da API, 422, sem conexão, nunca corpo cru de 500 |
| `formatos.spec.ts` | Quantidade e data pt-BR, sem deslocar o dia por fuso |
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
tabela `alembic_version` do PostgreSQL (deve ser a última, hoje `0002`).

**Migrations:** toda migration nova passa pelo ciclo `alembic upgrade head` →
`alembic downgrade -1` → `alembic upgrade head`, e `alembic check` não deve detectar diferença
entre modelos e banco.

## Lint e tipos

```bash
make lint      # ruff check + ruff format --check + vue-tsc + eslint
make verify    # lint + todos os testes — rodar antes de commitar
```
