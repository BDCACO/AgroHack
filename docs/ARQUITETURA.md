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

### Domínio e análise (motor de análise)

| Caminho | Responsabilidade | Regra |
|---|---|---|
| `app/domain/estoque.py` | Tipos de entrada (`Insumo`, `Lote`, `Retirada`), `Alerta` e as regras que não dependem de histórico: estoque abaixo do mínimo, lote vencido ou a vencer | **Sem I/O, sem banco, sem `datetime.now()`** — a data de referência entra como parâmetro |
| `app/analysis/consumo.py` | `analisar(...)`: consumo médio, cobertura em dias, risco de falta, excesso, baixa movimentação, consumo incomum e reposição estimada | Recebe listas, devolve `Analise` com **justificativa** em cada alerta e as **limitações** dos dados |

Os limiares (janela de 90 dias, 30 dias para vencimento, 180 de cobertura para excesso, prazo
padrão de 15 dias...) são constantes no topo de cada módulo, com o porquê ao lado. A análise usa
`statistics` da biblioteca padrão, não Pandas: média e desvio de uma lista de retiradas não
pedem DataFrame, e a conta fica legível para quem vai justificá-la ao produtor. A importação de
planilhas também não pediu: o `csv` da biblioteca padrão lê o CSV.

A resposta das rotas é o próprio `Analise` do motor (dataclass), sem schema espelho.

### Estoque (banco, serviço e rotas)

| Caminho | Responsabilidade |
|---|---|
| `app/models/estoque.py` | `insumos` e `movimentacoes` (entrada ou saída, data, quantidade, validade). **O estoque atual não é coluna**: é a soma das movimentações, calculada na leitura — uma fonte da verdade só |
| `app/services/estoque.py` | Casos de uso: cadastro, movimentações, a análise de cada insumo a partir do banco e o saldo dia a dia (histórico do gráfico). Única camada que as rotas de estoque chamam |
| `app/services/importacao.py` | Importação de movimentações por planilha CSV — ver abaixo |
| `app/demo.py` | Fazenda fictícia para a apresentação (`make demo`): insumos marcados com `demonstracao`, que a tela sinaliza e `make demo-limpar` apaga sozinhos |
| `app/core/relogio.py` | `hoje()` na data de Rondônia (UTC−4 fixo, sem horário de verão), não na do servidor |

Lote = entrada com validade. Como a retirada não diz de qual lote saiu, o saldo de cada lote é
estimado supondo que se usa primeiro o que vence primeiro (`lotes_em_estoque`), e a análise diz
isso nas limitações. Quantidades são `NUMERIC(12, 3)` no banco e `float` no Python.

### Importação de planilha

`POST /importacoes` recebe o texto do CSV (o navegador decodifica: UTF-8 ou, se falhar, o
Windows-1252 do Excel antigo) e devolve um resumo. Decisões:

- **Prévia antes de gravar.** Sem `confirmar`, só confere e resume — inclusive quanto entra e
  sai de cada insumo, que é onde um número lido errado salta aos olhos. A tela só então oferece
  importar. Se o confirmar falha sem resposta, a tela não oferece o mesmo botão (o servidor pode
  ter gravado): confere de novo, e `ja_lancadas` mostra se as linhas já estão lá.
- **Tudo ou nada.** Com um erro sequer, nada entra, e a resposta lista os erros por linha. Meia
  planilha importada deixaria o estoque errado sem ninguém perceber.
- **Formato do Excel em português e o internacional.** Separador de colunas `;` ou `,`
  (decidido pelo cabeçalho), datas DD/MM/AAAA (e AAAA-MM-DD), BOM.
- **O separador decimal é decidido pela planilha inteira**, não célula a célula: sozinho,
  `25.500` pode ser vinte e cinco e meio ou vinte e cinco mil. Células como `25,5`, `0.250` ou
  `1.234,5` revelam o formato; se nenhuma revela, vale o costume do arquivo (`;` → vírgula
  decimal, como o Excel em português; `,` → ponto decimal). Planilha que mistura os dois é erro.
- **Linha malformada é erro, não descarte.** Células a mais que o cabeçalho (a vírgula decimal
  num arquivo separado por vírgulas), aspa sem fechar (que junta o resto do arquivo numa célula)
  e caractere NUL viram erro com o número da linha.
- **Insumo pelo nome, sem diferenciar maiúsculas.** Nome novo vira insumo novo com a unidade da
  planilha (obrigatória nesse caso); unidade diferente da cadastrada é erro — somar kg com saca
  daria um estoque sem sentido. Se o cadastro tem dois nomes que só diferem em maiúsculas, a
  linha é erro: escolher um seria chute.
- **Planilha importada duas vezes vira aviso, não erro** (`ja_lancadas`): duas retiradas iguais
  no mesmo dia existem de verdade.
- Sem Excel (`.xlsx`): exigiria dependência nova; o "Salvar como CSV" resolve.

O fluxo é `rota → serviço → (domínio | análise) → ORM`. As setas só apontam para dentro:
`domain` e `analysis` não importam FastAPI nem SQLAlchemy. A exceção é `POST /analises`, que não
tem banco a orquestrar e chama o motor direto.

### Endpoints atuais

| Rota | O que faz |
|---|---|
| `GET /api/v1/health` | Liveness — o processo está no ar. Não toca o banco |
| `GET /api/v1/ready` | Readiness — `200` com o banco respondendo, `503` sem ele |
| `GET /api/v1/insumos` | Insumos com estoque atual e a análise de hoje (alertas, reposição, limitações) |
| `GET /api/v1/insumos/{id}` | Um insumo com a análise, o saldo no fim de cada dia com movimentação (`historico`) e as movimentações |
| `POST /api/v1/insumos` · `PUT /api/v1/insumos/{id}` | Cadastra / altera insumo (nome, unidade, mínimo, prazo de reposição). `409` para nome repetido |
| `DELETE /api/v1/insumos/{id}` | Remove o insumo cadastrado por engano, com as movimentações dele |
| `GET /api/v1/movimentacoes` | Entradas e saídas, as mais recentes primeiro (`insumo_id`, `limite`) |
| `POST /api/v1/movimentacoes` | Lança entrada ou saída. `422` para data futura, validade em saída ou insumo inexistente |
| `DELETE /api/v1/movimentacoes/{id}` | Remove lançamento errado |
| `POST /api/v1/importacoes` | Movimentações de uma planilha CSV. Sem `confirmar`, só confere e resume; com erro, nada é gravado e a resposta lista os erros por linha |
| `POST /api/v1/analises` | Roda o motor sobre um insumo enviado no corpo (estoque, retiradas, lotes, período) e devolve alertas, reposição e limitações. `422` para entrada inválida |
| `GET /api/v1/docs` | Swagger UI (desligado em `production`) |
| `GET /api/v1/openapi.json` | Schema OpenAPI (desligado em `production`) |

## 3. Frontend (`frontend/`)

| Caminho | Responsabilidade |
|---|---|
| `src/main.ts` | Instala Pinia e Router, importa o CSS |
| `src/router/` | Rotas. Páginas além do Painel entram por `import()` dinâmico. **O menu é derivado das rotas** (`meta.menu`): registrar uma tela é um lugar só |
| `src/layouts/` | `AppLayout`: menu lateral fixo no desktop, gaveta no celular, resumo de status |
| `src/pages/` | Uma página por rota: Painel (alertas, reposição com lista de compras para o WhatsApp, limitações), Insumos (cadastro), página do insumo (`/insumos/:id`: resumo, gráfico, alertas, movimentações, remover), Movimentações (entradas e saídas), Importar dados (CSV com prévia), Sistema |
| `src/components/` | Reutilizáveis, sem chamada à API: `CabecalhoDePagina`, `CartaoDeAlerta`, `EstadoVazio`, `GraficoDeEstoque`, `IconeSvg`, `IndicadorDeStatus`, `SeloDeGravidade` |
| `src/stores/` | Pinia — estado compartilhado e as ações que chamam os serviços. `estoque` guarda insumos (com a análise) e movimentações, e recarrega tudo a cada alteração |
| `src/services/http.ts` | **Cliente HTTP único** (Axios). Normaliza erro em `ApiError` |
| `src/services/*.ts` | Uma função por endpoint |
| `src/types/` | Tipos TypeScript dos contratos da API |
| `src/styles/main.css` | Tailwind v4 + tokens da marca (`@theme`) |
| `public/modelo-movimentacoes.csv` | Planilha modelo da importação, servida como arquivo estático (com BOM, para o Excel abrir os acentos) |
| `tests/unit/` | Vitest + Vue Test Utils |

Regras: componente `.vue` **não chama axios** (passa por `services/`) e **não decide** regra de
negócio — mostra o que a API calculou.

**Gráficos: Apache ECharts**, importado peça por peça (`echarts/core` + linha, grade, tooltip,
linhas de referência e o renderizador SVG), na página do insumo — que é carregada sob demanda,
então o Painel não paga o peso. O gráfico do estoque mostra o saldo em degraus (o saldo vale até
a próxima movimentação), a projeção tracejada no ritmo de consumo que a API calculou (até zerar,
no máximo 90 dias à frente) e a linha do mínimo. Texto digitado pelo usuário que vai para o
tooltip (HTML) é escapado; a tabela de movimentações ao lado é a versão acessível do gráfico.
A projeção usa a `cobertura_dias` da API com o mesmo arredondamento do cartão "Dura cerca de":
a página não pode dizer 8 dias num lugar e 9 no outro.

## 4. Infraestrutura

`compose.yaml` na raiz sobe `db` (PostgreSQL 18), `api` (imagem `backend/Dockerfile`, alvo `dev`,
com `--reload`) e `web` (Node 24 rodando o Vite). A API aplica `alembic upgrade head` ao subir
(`backend/docker/entrypoint.sh`); a espera pelo banco é o `healthcheck` do compose.

O Vite do container usa **polling** para perceber arquivos alterados (`VITE_POLLING` no
compose): no Docker Desktop do Windows, o código montado do host não gera eventos de arquivo
dentro do container, e sem isso o Vite serve a versão antiga até reiniciar.

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
| Tipos TS gerados do OpenAPI | Escritos à mão (por ora) | Poucos recursos; geração entra quando a API crescer |
| Dois stacks compose + rede `edge` | Um compose só | Sem serviços internos (MinIO, Redis, worker) a isolar |
| MinIO, Redis, worker, ClamAV, rate-limit, auth com sessão | — | Nenhum requisito do CampoCerto pede, por ora |
| mypy strict, import-linter, dependency-cruiser, cobertura 90% | ruff + vue-tsc + eslint | Proporcional ao tamanho; os gates entram se as regras de camada começarem a ser violadas |

## 6. Próximas decisões (pendentes)

1. **Autenticação** — o desafio não exige; decidir se a demonstração é monousuário. Hoje qualquer
   um que alcance a tela lê e altera tudo (as portas da API e do banco ficam só em 127.0.0.1; a do
   front fica aberta na rede).
2. **Geração de tipos TS a partir do OpenAPI** (`openapi-typescript`) quando a API crescer.
3. **Importação de `.xlsx`**, se o "Salvar como CSV" do Excel atrapalhar quem testar.

Decididas desde a versão anterior deste documento: a importação de planilha existe (CSV, seção
2); o ECharts entrou com o gráfico do insumo; o Pandas não entrou — nem o motor de análise nem a
importação precisaram.
