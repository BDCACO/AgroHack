# Arquitetura do CampoCerto

Plataforma de gestão inteligente de insumos rurais (AGROHACK 2026/2, IFRO Campus Ariquemes).
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
| `app/main.py` | Fábrica `create_app(settings)`: os testes criam a sua com configuração própria |
| `app/core/config.py` | `Settings` (pydantic-settings). Única fonte de variáveis de ambiente |
| `app/core/database.py` | Engine, sessão e a dependência `get_db` |
| `app/api/router.py` | Agrega as rotas da v1 (`/api/v1`) |
| `app/api/routes/` | Rotas HTTP, finas: validam entrada, chamam serviço, devolvem schema |
| `app/schemas/` | Modelos Pydantic de entrada/saída da API |
| `app/models/` | Modelos ORM (SQLAlchemy). Todo modelo novo é importado em `models/__init__.py` |
| `migrations/` | Alembic. Linhagem única, toda migration com `downgrade` |
| `tests/` | Pytest |

### Domínio e análise (motor de análise)

| Caminho | Responsabilidade | Regra |
|---|---|---|
| `app/domain/estoque.py` | Tipos de entrada (`Insumo`, `Lote`, `Retirada`), `Alerta` e as regras que não dependem de histórico: estoque abaixo do mínimo, lote vencido ou a vencer | **Sem I/O, sem banco, sem `datetime.now()`**: a data de referência entra como parâmetro |
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
| `app/models/estoque.py` | `insumos` e `movimentacoes` (entrada ou saída, data, quantidade, validade). **O estoque atual não é coluna**: é a soma das movimentações, calculada na leitura. Uma fonte da verdade só |
| `app/services/estoque.py` | Casos de uso: cadastro, movimentações, a análise de cada insumo a partir do banco e o saldo dia a dia (histórico do gráfico). As rotas falam só com os serviços (este, `importacao`, `planilha_modelo` e `relatorio`) |
| `app/services/importacao.py` | Importação de movimentações por planilha (Excel ou CSV), ver abaixo |
| `app/services/planilha_modelo.py` | A planilha modelo da importação e os estilos das planilhas geradas (cores da marca, títulos, impressão) |
| `app/services/relatorio.py` | O relatório em Excel: resumo, alertas, reposição, situação de cada insumo e todas as movimentações |
| `app/demo.py` | Fazenda fictícia para a apresentação (`make demo`): insumos marcados com `demonstracao`, que a tela sinaliza e `make demo-limpar` apaga sozinhos |
| `app/core/relogio.py` | `hoje()` na data de Rondônia (UTC−4 fixo, sem horário de verão), não na do servidor |

Lote = entrada com validade. Como a retirada não diz de qual lote saiu, o saldo de cada lote é
estimado supondo que se usa primeiro o que vence primeiro (`lotes_em_estoque`), e a análise diz
isso nas limitações. Quantidades são `NUMERIC(12, 3)` no banco e `float` no Python.

### Importação de planilha

`POST /importacoes` recebe a planilha do Excel (`.xlsx`, em base64 no JSON) ou o texto de um CSV
(o navegador decodifica: UTF-8 ou, se falhar, o Windows-1252 do Excel antigo) e devolve um
resumo. Os dois formatos viram cabeçalho + linhas de células e passam pelas mesmas regras
(`app/services/importacao.py`). O guia para quem preenche está em
[`IMPORTACAO.md`](IMPORTACAO.md). Decisões:

- **Prévia antes de gravar.** Sem `confirmar`, só confere e resume, inclusive quanto entra e
  sai de cada insumo, que é onde um número lido errado salta aos olhos. A tela só então oferece
  importar. Se o confirmar falha sem resposta, a tela não oferece o mesmo botão (o servidor pode
  ter gravado): confere de novo, e `ja_lancadas` mostra se as linhas já estão lá.
- **Tudo ou nada.** Com um erro sequer, nada entra, e a resposta lista os erros por linha. Meia
  planilha importada deixaria o estoque errado sem ninguém perceber.
- **`.xlsx` é o formato principal.** Data e número chegam com tipo, sem a dúvida de vírgula ou
  ponto, e o produtor não precisa converter nada. Lê a aba **Movimentações** (a do modelo e a
  do relatório) ou, se não houver, a primeira; o número da linha nos erros é o do Excel.
- **Upload é entrada hostil.** Um `.xlsx` é um zip de XML: pequeno compactado, pode ser enorme
  aberto. Por isso, em camadas: pedido acima de 8 MB recusado com `413` antes de ler o corpo
  (`app/main.py`; pelo proxy do Vite essa recusa antecipada chega como `502`, porque o proxy
  ainda estava enviando; a tela já barra arquivo acima de 5 MB antes de enviar, e em produção
  o proxy reverso deve ter o próprio limite, como o `client_max_body_size` do nginx); arquivo
  de até 5 MB; conteúdo descompactado de até 50 MB (conferido no
  índice do zip, antes de abrir); `defusedxml` instalado, que o `openpyxl` usa sozinho contra
  XML malicioso; leitura em `read_only` (linha a linha) **ignorando a dimensão gravada no
  arquivo**, que pode mentir (menor, cortaria linhas sem aviso; enorme, faria o leitor
  preencher milhões de células vazias); e tetos de 1.048.576 linhas (o do Excel), 5 milhões
  de células lidas e 50 mil movimentações.
- **CSV: o do Excel em português e o internacional.** Separador de colunas `;` ou `,`
  (decidido pelo cabeçalho), datas DD/MM/AAAA (e AAAA-MM-DD), BOM.
- **O separador decimal é decidido pela planilha inteira**, não célula a célula: sozinho,
  `25.500` pode ser vinte e cinco e meio ou vinte e cinco mil. Células como `25,5`, `0.250` ou
  `1.234,5` revelam o formato; se nenhuma revela, vale o costume do arquivo (`;` → vírgula
  decimal, como o Excel em português; `,` → ponto decimal). Planilha que mistura os dois é erro.
- **Linha malformada é erro, não descarte.** Células a mais que o cabeçalho (a vírgula decimal
  num arquivo separado por vírgulas), aspa sem fechar (que junta o resto do arquivo numa célula)
  e caractere NUL viram erro com o número da linha.
- **Insumo pelo nome, sem diferenciar maiúsculas.** Nome novo vira insumo novo com a unidade da
  planilha (obrigatória nesse caso); unidade diferente da cadastrada é erro: somar kg com saca
  daria um estoque sem sentido. Se o cadastro tem dois nomes que só diferem em maiúsculas, a
  linha é erro: escolher um seria chute.
- **Planilha importada duas vezes vira aviso, não erro** (`ja_lancadas`): duas retiradas iguais
  no mesmo dia existem de verdade.
- **Planilha modelo gerada na hora** (`GET /importacoes/modelo.xlsx`,
  `app/services/planilha_modelo.py`), não um arquivo parado no repositório: vem com os insumos
  cadastrados (aba própria, que alimenta a lista de escolha da coluna `insumo`) e com exemplos
  de datas recentes. Formatada para preencher certo: cabeçalho nas cores da marca com a
  explicação de cada coluna em comentário, datas DD/MM/AAAA na coluna inteira e validação do
  próprio Excel até a linha 50.001: data, tipo, quantidade e validade **barram** valor errado
  (`showErrorMessage`, que o `openpyxl` deixa desligado por padrão); insumo e unidade só
  sugerem da lista, porque insumo novo vale. Nome de insumo é gravado sempre como texto (um
  "=1+1" não vira fórmula) e sem caractere de controle, que o cadastro e a importação também
  recusam. `.xls`, `.ods` e `.numbers` não são aceitos: a tela diz como converter.

O fluxo é `rota → serviço → (domínio | análise) → ORM`. As setas só apontam para dentro:
`domain` e `analysis` não importam FastAPI nem SQLAlchemy. A exceção é `POST /analises`, que não
tem banco a orquestrar e chama o motor direto.

### Endpoints atuais

| Rota | O que faz |
|---|---|
| `GET /api/v1/health` | Liveness: o processo está no ar. Não toca o banco |
| `GET /api/v1/ready` | Readiness: `200` com o banco respondendo, `503` sem ele |
| `GET /api/v1/insumos` | Insumos com estoque atual e a análise de hoje (alertas, reposição, limitações) |
| `GET /api/v1/insumos/{id}` | Um insumo com a análise, o saldo no fim de cada dia com movimentação (`historico`) e as movimentações |
| `POST /api/v1/insumos` · `PUT /api/v1/insumos/{id}` | Cadastra / altera insumo (nome, unidade, mínimo, prazo de reposição). `409` para nome repetido |
| `DELETE /api/v1/insumos/{id}` | Remove o insumo cadastrado por engano, com as movimentações dele |
| `GET /api/v1/movimentacoes` | Entradas e saídas, as mais recentes primeiro (`insumo_id`, `limite`) |
| `POST /api/v1/movimentacoes` | Lança entrada ou saída. `422` para data futura, validade em saída ou insumo inexistente |
| `DELETE /api/v1/movimentacoes/{id}` | Remove lançamento errado |
| `POST /api/v1/importacoes` | Movimentações de uma planilha: `xlsx` (base64) ou `conteudo` (texto do CSV). Sem `confirmar`, só confere e resume, com o total de cada insumo; com erro, nada é gravado e a resposta lista os erros por linha |
| `GET /api/v1/importacoes/modelo.xlsx` | Planilha modelo formatada, com os insumos cadastrados para escolher da lista |
| `GET /api/v1/relatorio.xlsx` | Relatório do estoque em Excel. A aba Movimentações tem o formato da importação: é também a cópia de segurança, e volta pela mesma tela |
| `POST /api/v1/analises` | Roda o motor sobre um insumo enviado no corpo (estoque, retiradas, lotes, período) e devolve alertas, reposição e limitações. `422` para entrada inválida |
| `GET /api/v1/docs` | Swagger UI (desligado em `production`) |
| `GET /api/v1/openapi.json` | Schema OpenAPI (desligado em `production`) |

## 3. Frontend (`frontend/`)

| Caminho | Responsabilidade |
|---|---|
| `src/main.ts` | Instala Pinia e Router, importa o CSS |
| `src/router/` | Rotas. Páginas além do Painel entram por `import()` dinâmico. **O menu é derivado das rotas** (`meta.menu`): registrar uma tela é um lugar só |
| `src/layouts/` | `AppLayout`: menu lateral fixo no desktop, gaveta no celular, resumo de status |
| `src/pages/` | Uma página por rota: Painel (alertas, reposição com lista de compras para o WhatsApp, limitações), Insumos (cadastro), página do insumo (`/insumos/:id`: resumo, gráfico, alertas, movimentações, remover), Movimentações (entradas e saídas), Importar dados (Excel ou CSV, com prévia), Sistema |
| `src/components/` | Reutilizáveis, sem chamada à API: `CabecalhoDePagina`, `CartaoDeAlerta`, `CoberturaDoEstoque` (quanto tempo cada insumo dura), `EstadoVazio`, `GraficoDeEstoque`, `IconeSvg`, `IndicadorDeStatus`, `LogoCampoCerto`, `NumeroRolante`, `SeloDeGravidade` |
| `src/stores/` | Pinia: estado compartilhado e as ações que chamam os serviços. `estoque` guarda insumos (com a análise) e movimentações, e recarrega tudo a cada alteração |
| `src/services/http.ts` | **Cliente HTTP único** (Axios). Normaliza erro em `ApiError` |
| `src/services/*.ts` | Uma função por endpoint |
| `src/types/` | Tipos TypeScript dos contratos da API |
| `src/styles/main.css` | Tailwind v4: tokens da marca e de movimento (`@theme`), componentes base (`.cartao`, `.botao-*`, `.campo`, `.esqueleto`) e as transições (ver "Design e movimento") |
| `public/modelo-movimentacoes.csv` | Modelo alternativo em CSV, servido como arquivo estático (com BOM, para o Excel abrir os acentos); o principal é o `.xlsx` gerado pela API |
| `tests/unit/` | Vitest + Vue Test Utils |

Regras: componente `.vue` **não chama axios** (passa por `services/`) e **não decide** regra de
negócio: mostra o que a API calculou.

### Design e movimento

Visual calmo e terroso: verde de lavoura (`campo`, de 50 a 950) como cor da marca, terra e
palha (`terra`) como acento quente, fundo de pedra clara, cartões brancos. Fonte **Plus Jakarta
Sans** (`@fontsource-variable`), embutida no app: funciona sem internet, como numa apresentação.
Tudo mora em `main.css`: as cores, a fonte, as curvas e durações de animação e os componentes
base. Botão e cartão são classes (`.botao-primario`, `.cartao`...), não estilo repetido em cada
tela.

**Animação só onde informa.** Só `transform` e `opacity` (a placa de vídeo anima sem refazer a
página), e uma curva para cada tipo de movimento:

| Curva | Uso | Duração típica |
|---|---|---|
| `ease-chegada` | o que entra na tela: desacelera ao chegar | 200 a 300 ms |
| `ease-saida` | o que sai: acelera ao ir embora, mais rápido que a entrada | 90 a 200 ms |
| `ease-movimento` | o que já está na tela e muda de lugar: acelera e freia | 250 a 300 ms |

Hover fica em 150 ms; o botão afunda para 97% em 100 ms ao ser apertado, que no celular é o que
diz que o dedo pegou.

- **O que mudou:** os números de gravidade rolam dígito a dígito até o valor, como um contador
  mecânico (`NumeroRolante`); parado, o número fica exatamente onde um texto comum ficaria. A
  linha recém-lançada em Movimentações acende e esmaece.
- **Onde você está:** o destaque da página atual no menu é um só e desliza até o item novo; o
  fundo do seletor Saída/Entrada também desliza.
- **Ordem de leitura:** alertas chegam em cascata (40 ms entre um e outro, até o oitavo), os mais
  graves primeiro; as barras de "quanto tempo o estoque dura" crescem da esquerda, da mais
  apertada à mais folgada; a linha do gráfico se desenha no sentido do tempo.
- **Para onde foi:** ao filtrar alertas, quem fica desliza para o lugar e quem sai esmaece
  encolhendo um pouco. A gaveta do celular entra em 300 ms e sai em 200 ms.
- **Trabalho em andamento e resultado:** barra de "trabalhando" ao conferir a planilha, ícone
  que gira ao verificar o sistema, sinal de concluído que se desenha, esqueleto no lugar do
  conteúdo que está chegando.
- **O que não pode esperar:** só o ponto do selo "Urgente" pulsa (uma cópia dele cresce e
  some). Nada mais anima em loop.

Quem pede **menos movimento** ao sistema operacional (`prefers-reduced-motion`) não recebe
animação nenhuma: a regra global em `main.css` zera as durações e toda tela aparece já no estado
final, números inclusive.

**Gráficos: Apache ECharts**, importado peça por peça (`echarts/core` + linha, grade, tooltip,
linhas de referência e o renderizador SVG), na página do insumo, que é carregada sob demanda,
então o Painel não paga o peso. O gráfico do estoque mostra o saldo em degraus (o saldo vale até
a próxima movimentação), a projeção tracejada no ritmo de consumo que a API calculou (até zerar,
no máximo 90 dias à frente) e a linha do mínimo. Texto digitado pelo usuário que vai para o
tooltip (HTML) é escapado; a tabela de movimentações ao lado é a versão acessível do gráfico.
A projeção usa a `cobertura_dias` da API com o mesmo arredondamento do cartão "Dura cerca de":
a página não pode dizer 8 dias num lugar e 9 no outro.

## 4. App para celular (`mobile/`)

App nativo em Flutter para Android e iOS, além do site. Fala com a mesma API e segue a mesma
regra: **exibe e coleta**, a análise fica no backend. O app espelha o desenho do frontend:

| Caminho | Responsabilidade | No site |
|---|---|---|
| `lib/core/api/cliente_api.dart` | Cliente HTTP único; devolve `ApiError` com a frase para a tela | `services/http.ts` |
| `lib/models/api.dart` | Espelho dos schemas da API, escrito à mão | `types/api.ts` |
| `lib/services/estoque.dart` | Rotas de insumos, movimentações e `/ready` | `services/estoque.ts`, `health.ts` |
| `lib/pages/` | Painel, Insumos, Movimentações, Importar, Sistema | `pages/` |
| `lib/core/tema.dart` | Cores da marca, rótulos de alerta e de gravidade | `main.css`, `SeloDeGravidade.vue`, `CartaoDeAlerta.vue` |

Decisões:

- **Endereço da API no build** (`--dart-define=API_URL=...`). O app não vive na mesma origem
  da API como o site. O padrão é `http://10.0.2.2:8000/api/v1`, o `localhost` do computador
  visto do emulador do Android.
- **`http://` só em desenvolvimento.** O Android aceita tráfego sem TLS só no build de debug; o
  iOS, só na rede local. O release exige `https://`.
- **Sem gerenciador de estado nem roteador de pacote.** Cinco telas numa barra embaixo e um
  `InheritedWidget` (`Servicos`) com os serviços bastam hoje; nos testes, troca-se o cliente
  HTTP por um falso num lugar só. Entra Riverpod ou go_router quando a navegação pedir.
- **Mudou um schema na API, muda em três lugares**: `backend/app/schemas/`, `types/api.ts` e
  `models/api.dart`. Gerar a partir do OpenAPI resolveria os dois últimos (seção 7).

Ainda não há no app: página do insumo com o gráfico, cadastro, lançamento de movimentação e
importação de planilha (falta escolher o arquivo no celular). Para esses, use o site.

## 5. Infraestrutura

`compose.yaml` na raiz sobe `db` (PostgreSQL 18), `api` (imagem `backend/Dockerfile`, alvo `dev`,
com `--reload`) e `web` (Node 24 rodando o Vite). A API aplica `alembic upgrade head` ao subir
(`backend/docker/entrypoint.sh`); a espera pelo banco é o `healthcheck` do compose.

O Vite do container usa **polling** para perceber arquivos alterados (`VITE_POLLING` no
compose): no Docker Desktop do Windows, o código montado do host não gera eventos de arquivo
dentro do container, e sem isso o Vite serve a versão antiga até reiniciar.

Configuração por `.env` na raiz (modelo em `.env.example`). Variáveis obrigatórias sem default:
`ENVIRONMENT` e `DATABASE_URL` (montada pelo compose a partir de `POSTGRES_*`).

## 6. Herdado do ArkoHub × decidido diferente

O ArkoHub é um SaaS multi-tenant de ferramentas para escritórios (FastAPI + Vue 3/Vuetify +
PostgreSQL com RLS + MinIO + Redis + worker). O CampoCerto aproveita os **padrões**, não as
tecnologias que não se aplicam.

**Aproveitado**

- Monorepo `backend/` + `frontend/` com responsabilidades separadas; FastAPI como fonte da verdade
  do contrato.
- `Settings` com pydantic-settings, validado no boot, **`ENVIRONMENT` obrigatório e restrito** a
  valores conhecidos (fail-closed) e `/docs` desligado em produção.
- Separação **liveness (`/health`) × readiness (`/ready`)**.
- Front e API na mesma origem via proxy do Vite, sem CORS.
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
| SQLAlchemy **async** + asyncpg/psycopg | SQLAlchemy **síncrono** + psycopg 3 | A análise e a leitura de planilhas são CPU-bound e síncronas; rotas `def` rodam em threadpool |
| Alembic sem autogenerate (`target_metadata=None`) | Autogenerate ligado, migration **revisada** | Lá o motivo era RLS invisível ao autogenerate; aqui não existe |
| Vuetify | Tailwind CSS v4 | Stack definida para o projeto |
| openapi-fetch + TanStack Query | Axios + Pinia | Stack definida para o projeto |
| Tipos TS gerados do OpenAPI | Escritos à mão (por ora) | Poucos recursos; geração entra quando a API crescer |
| Dois stacks compose + rede `edge` | Um compose só | Sem serviços internos (MinIO, Redis, worker) a isolar |
| MinIO, Redis, worker, ClamAV, rate-limit, auth com sessão | Não entrou | Nenhum requisito do CampoCerto pede, por ora |
| mypy strict, import-linter, dependency-cruiser, cobertura 90% | ruff + vue-tsc + eslint | Proporcional ao tamanho; os gates entram se as regras de camada começarem a ser violadas |

## 7. Próximas decisões (pendentes)

1. **Autenticação.** O desafio não exige; decidir se a demonstração é monousuário. Hoje qualquer
   um que alcance a tela lê e altera tudo (as portas da API e do banco ficam só em 127.0.0.1; a do
   front fica aberta na rede).
2. **Geração de tipos TS a partir do OpenAPI** (`openapi-typescript`) quando a API crescer. Com o
   app, os modelos em Dart entram na mesma conta.
3. **App nas lojas.** Ícone, assinatura do Android, conta de desenvolvedor da Apple e a API em
   `https://` em algum endereço público.

Decididas desde a versão anterior deste documento: a importação de planilha existe (Excel e
CSV, seção 2); o ECharts entrou com o gráfico do insumo; o Pandas não entrou, porque nem o motor de
análise nem a importação precisaram; o `openpyxl` entrou para ler e gerar `.xlsx`.
