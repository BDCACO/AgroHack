# Testes

## Backend — Pytest (`backend/tests/`)

A suíte usa **SQLite em memória** (`DATABASE_URL=sqlite://`, definido em `tests/conftest.py`),
então não precisa de Docker nem de PostgreSQL. A fixture `db` cria as tabelas dos modelos num
banco novo por teste, com `FOREIGN KEY` ligada (como no PostgreSQL), e `client` usa esse banco
no lugar do `get_db`.

| Arquivo | Cobre |
|---|---|
| `test_health.py` | `/health` responde; `/ready` dá 200 com banco e **503** quando o banco falha |
| `test_config.py` | `ENVIRONMENT` obrigatório e restrito; `/docs` ligado fora de produção e desligado em produção |
| `test_estoque.py` | Cadastro de insumo (nome repetido = `409`), estoque e análise calculados das movimentações, movimentação inválida (`422`), alteração, listagem e remoção; detalhe do insumo com o saldo dia a dia; remover insumo leva as movimentações |
| `test_importacao.py` | **CSV:** planilha do Excel em português (BOM, `;`, vírgula decimal, `1.000`, DD/MM/AAAA); prévia não grava e traz o total de cada insumo; confirmar grava e cadastra insumos novos; reimportar avisa `ja_lancadas`; separador decimal decidido pela planilha inteira (`0.250`, `25.500`, `1,234.5`) e planilha que mistura os dois; células a mais, aspa sem fechar (inclusive estourando o limite do `csv`); unidade diferente da cadastrada; nomes do cadastro que só diferem em maiúsculas; com um erro, nada é gravado — e cada erro diz a linha; planilha vazia ou sem as colunas. **Excel (.xlsx):** a planilha modelo vem formatada (títulos, comentários, formato de data na coluna, validações que barram e listas que só sugerem) e com os insumos cadastrados, gravados como texto mesmo com "=" ou caractere de controle; o modelo preenchido volta pela importação, com data e número tipados ou digitados como texto; o exemplo do próprio modelo importa sem erro; modelo vazio não tem o que importar; os erros apontam a linha do Excel (inclusive número de série no lugar da data e valor em coluna sem título); arquivo que não é `.xlsx`; pedido sem arquivo ou com os dois formatos. **Arquivo hostil:** dimensão gravada errada não corta a importação; planilha inflada (linha além do limite do Excel) é recusada em segundos; conteúdo descompactado acima do teto; pedido acima de 8 MB recusado com `413` antes de ler o corpo; nome com caractere de controle recusado no cadastro e na importação; valor em coluna sem título diz a letra da coluna |
| `test_relatorio.py` | Relatório em Excel com a fazenda de demonstração: abas, alertas dos mais graves aos mais leves, reposição, situação de cada insumo; a aba Movimentações volta pela importação (tudo já lançado); sem nada cadastrado |
| `test_demo.py` | A fazenda de demonstração acende os alertas do roteiro, insumo por insumo; recarregar substitui; limpar apaga só a demonstração |
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
| `estoque.spec.ts` | Store: alertas de todos os insumos, os mais graves primeiro; recarga após lançar movimentação; mensagem legível sem API. Painel: alertas com justificativa, reposição, lista de compras do WhatsApp ("Pedir agora" separado dos próximos), cartões de gravidade que filtram a lista, barras de cobertura (falta, pedir hoje, folga) em ordem, estado vazio |
| `importacao.spec.ts` | Tela de importação: CSV decodificado do Windows-1252, `.xlsx` enviado em base64, `.xls`, `.ods`, `.numbers` e formato desconhecido barrados com a instrução do que fazer; mostra o resumo e os totais, só grava ao confirmar e recarrega o estoque; com erros, lista-os e não oferece importar; se o confirmar falha, não oferece o mesmo botão e confere de novo; o link do modelo aponta para a planilha da API |
| `insumo.spec.ts` | Página do insumo: resumo, alertas sem repetir o nome, "Insumos" aceso no menu, alertas mesmo sem movimentação, remover e voltar à lista. Gráfico (ECharts substituído por um mock que guarda a configuração): saldo mantido até hoje, projeção com a mesma cobertura do cartão, texto do usuário escapado no tooltip |
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
tabela `alembic_version` do PostgreSQL (deve ser a última migration de
`backend/migrations/versions/`).

## No GitHub (CI)

`.github/workflows/verificacao.yml` roda o mesmo que o `make verify` — ruff, pytest, vue-tsc,
eslint e vitest — em todo PR e em todo push na `main`, direto com uv e Node (sem Docker). PR com
a verificação vermelha não deve ser mergeado.

## Lint e tipos

```bash
make lint      # ruff check + ruff format --check + vue-tsc + eslint
make verify    # lint + todos os testes — rodar antes de commitar
```
