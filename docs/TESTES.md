# Testes

## Backend: Pytest (`backend/tests/`)

A suíte usa **SQLite em memória** (`DATABASE_URL=sqlite://`, definido em `tests/conftest.py`),
então não precisa de Docker nem de PostgreSQL. A fixture `db` cria as tabelas dos modelos num
banco novo por teste, com `FOREIGN KEY` ligada (como no PostgreSQL), e `client` usa esse banco
no lugar do `get_db`. A suíte roda com a autenticação **desligada** (`AUTENTICACAO=false`,
forçado no `conftest.py`); os testes de login usam `cliente_autenticado`, a mesma API com ela
ligada, e `criar_usuario`, que grava o usuário direto no banco com um hash de senha calculado
uma vez só (o scrypt leva uns 0,2 s de propósito).

| Arquivo | Cobre |
|---|---|
| `test_health.py` | `/health` responde; `/ready` dá 200 com banco e **503** quando o banco falha |
| `test_config.py` | `ENVIRONMENT` obrigatório e restrito; `/docs` ligado fora de produção e desligado em produção; em produção, `AUTENTICACAO` ausente ou `false` impede a API de subir; desligada por padrão em development e test; valor que não é verdadeiro ou falso é recusado; aviso no log ao subir desligada |
| `test_senha.py` | Hash scrypt com os parâmetros e sem a senha; sal diferente a cada hash; senha certa e errada; acento composto ou decomposto é a mesma senha; hash com outro custo ainda confere e pede para refazer; hash ilegível não confere nem derruba |
| `test_autenticacao.py` | Login devolve o token uma vez, guarda só o SHA-256 e vale 30 dias; login sem diferenciar maiúsculas e espaços; senha errada, login inexistente e usuário desativado com a mesma resposta, e o inexistente gastando o mesmo scrypt; sem token, token falso e esquema `Basic` dão `401` com `WWW-Authenticate`; sessão vencida (relógio trocado, sem dormir); sair encerra só a sessão atual; trocar a senha encerra as outras e exige a atual e 8 caracteres; usuário desativado perde a sessão; `/auth/eu` exige login mesmo desligada. **Bloqueio:** 5 erros bloqueiam por 15 minutos (a sexta, certa, recusada com a mesma frase; no banco), tentar durante o bloqueio não o estende, acertar zera, senha atual errada na troca conta, o dono vê o bloqueio e a senha redefinida o desfaz |
| `test_permissoes.py` | **Todas as rotas do app** (percorridas pelo `iter_route_contexts` do FastAPI) estão na matriz, cada uma no seu nível; e, por HTTP, rota a rota: ligada, sem token e com token falso `401` (menos as públicas), funcionário `403` só no que é do dono, dono passa; desligada, sem token passa (menos sessão e gestão de usuários), token falso `401`, funcionário `403` no que é do dono |
| `test_usuarios.py` | `/usuarios`: o dono cadastra o funcionário (login aparado e em minúsculas), que entra com a senha dada; login repetido sem diferenciar maiúsculas `409`; login com acento, espaço ou curto, senha curta, papel desconhecido e nome em branco ou com caractere de controle `422`; alterar só o que veio; desativar derruba as sessões e o login, reativar deixa entrar de novo; o último dono ativo não se desativa nem vira funcionário (dono inativo não conta); redefinir a senha derruba as sessões; `404` |
| `test_auditoria.py` | `usuario_id` e `lancado_por` no POST (o `usuario_id` do corpo é ignorado), na listagem, no detalhe do insumo, na fila do app, na contagem do galpão e na importação; o reenvio por outro usuário mantém o autor; desligada e sem login, `null` |
| `test_usuarios_cli.py` | `python -m app.usuarios criar-dono`: senha pela variável de ambiente (sem aparecer na saída) ou pelo terminal, duas vezes; confirmação diferente não cria; com dono ativo só com `--outro-dono`, e dono desativado não impede; login, senha e nome inválidos explicados; login já usado |
| `test_estoque.py` | Cadastro de insumo (nome repetido = `409`), estoque e análise calculados das movimentações, movimentação inválida (`422`), alteração, listagem e remoção; detalhe do insumo com o saldo dia a dia; remover insumo leva as movimentações; descarte tira o lote vencido sem virar consumo; inventário com falta, com sobra, com contagem que bate (comparada ao saldo do dia da contagem) e inválido; ajuste de inventário só pela contagem; compras com preço dão custo médio e valor em estoque (estoque negativo vale zero); compra sem preço fica fora do custo e a análise diz; preço em saída ou descarte, zero ou negativo é `422` com a explicação; embalagem e pedido mínimo inválidos; `PUT` sem os campos novos mantém a embalagem |
| `test_importacao.py` | **CSV:** planilha do Excel em português (BOM, `;`, vírgula decimal, `1.000`, DD/MM/AAAA); prévia não grava e traz o total de cada insumo; confirmar grava e cadastra insumos novos; reimportar avisa `ja_lancadas`; separador decimal decidido pela planilha inteira (`0.250`, `25.500`, `1,234.5`) e planilha que mistura os dois; células a mais, aspa sem fechar (inclusive estourando o limite do `csv`); unidade diferente da cadastrada; nomes do cadastro que só diferem em maiúsculas; com um erro, nada é gravado, e cada erro diz a linha; planilha vazia ou sem as colunas. **Excel (.xlsx):** a planilha modelo vem formatada (títulos, comentários, formato de data na coluna, validações que barram e listas que só sugerem) e com os insumos cadastrados, gravados como texto mesmo com "=" ou caractere de controle; o modelo preenchido volta pela importação, com data e número tipados ou digitados como texto; o exemplo do próprio modelo importa sem erro; modelo vazio não tem o que importar; os erros apontam a linha do Excel (inclusive número de série no lugar da data e valor em coluna sem título); arquivo que não é `.xlsx`; pedido sem arquivo ou com os dois formatos. **Arquivo hostil:** dimensão gravada errada não corta a importação; planilha inflada (linha além do limite do Excel) é recusada em segundos; conteúdo descompactado acima do teto; pedido acima de 8 MB recusado com `413` antes de ler o corpo; nome com caractere de controle recusado no cadastro e na importação; valor em coluna sem título diz a letra da coluna. **Preço (`valor`):** entra nas compras e dá o custo médio (com "R$"); em saída, descarte, falta ou sobra, ou não sendo número maior que zero, é erro na linha; decide o separador decimal junto com a quantidade; reimportar a mesma compra com outro preço não conta como já lançada; a coluna no modelo (formato de moeda, validação que barra) |
| `test_sincronizacao.py` | Lançamento offline do app: `uuid` gravado e devolvido; sem ele, como antes (dois iguais são dois); reenvio devolve o gravado com `200` (inclusive quantidade com mais casas que o banco guarda); mesmo uuid com outro conteúdo é `409` com os campos que diferem; removido e reenviado grava de novo; violação do `UNIQUE` (envio simultâneo, simulado) vira reenvio e não `500`. Lote: grava na ordem e o reenvio volta `ja_existia`; item ruim (quantidade negativa, sem uuid, data e tipo inválidos, data futura, insumo inexistente, uuid com outro conteúdo, item que não é objeto, uuid ilegível) é `recusada` com frases em português e os outros gravam; 500 cabem, 501 é `422`; avisos de estoque negativo no fim do lote (uma vez por insumo), data atrasada e lançamento igual feito sem o app, devolvidos também no reenvio |
| `test_talhao.py` | Domínio do talhão, sem banco: a colheita libera no maior data + carência (e não na aplicação mais recente), no próprio dia já pode colher, alerta de gravidade alta com a conta ("faltam 9 dias", "falta 1 dia"), aplicação futura fora da conta, insumo sem carência cadastrada vira limitação com os nomes (0 é "não tem"); custo pela quantidade × custo médio, por hectare e por insumo (o que mais pesou primeiro), recorte de período com os extremos, aplicação sem preço fora do custo e na limitação, `None` (e não zero) sem preço nenhum |
| `test_talhoes.py` | `/talhoes`: cadastro (nome aparado, cultura opcional e em branco vira vazia, área zero, negativa ou acima do `NUMERIC(10, 2)`, caractere de controle, nome repetido `409`), alterar, detalhar, remover (`404`); retirada lançada no talhão (e no lote do app), talhão em entrada ou descarte e talhão inexistente `422`, no lote `recusada` com frase; reenvio com outro talhão `409`; talhão com aplicação não se remove (`409`); `carencia_dias` no insumo (0 a 365, inteiro) e o `PUT` sem ela mantém a gravada; leitura com carência, custo total e por hectare, limitações, detalhe com aplicações e consumo, recorte da safra (a carência não muda com ele), período invertido `422`; planilha com a coluna `talhao` (sem diferenciar maiúsculas, `talhão` com acento, só em saída, talhão não cadastrado é erro na linha), modelo com a coluna, a lista e a aba Talhões cadastrados; relatório com a aba Talhões e a cópia de segurança com o talhão de cada aplicação |
| `test_relatorio.py` | Relatório em Excel com a fazenda de demonstração: abas, alertas dos mais graves aos mais leves, reposição, situação de cada insumo; a aba Movimentações volta pela importação (tudo já lançado, inclusive descarte, sobra, falta, o preço das compras e o talhão das aplicações); em reais: custo médio e valor em estoque, custo estimado da reposição e os totais do resumo; sem nada cadastrado |
| `test_resumo.py` | `GET /resumo`: sem nada cadastrado; valor em estoque, perdas (descarte e falta da contagem, nos últimos 30 dias e no total) pelo custo médio, compras sugeridas dos próximos 30 dias, alertas por gravidade (só os dos insumos) e as limitações quando há insumo sem preço; talhões em carência contados à parte |
| `test_demo.py` | A fazenda de demonstração acende os alertas do roteiro, insumo por insumo; fala em reais (todo insumo com custo médio, vencimento e excesso com valor, ureia em sacos de 50 kg com custo da compra); recarregar substitui; limpar apaga só a demonstração, insumos e talhões (menos o talhão com aplicação de um insumo real); um talhão só (o Norte) em carência no dia da carga, com a data e o insumo certos, custo por hectare em todos e a limitação do calcário sem carência |
| `test_analises.py` | `POST /analises`: resposta com alertas, reposição e limitações; `custo_medio` opcional põe reais nos alertas; `422` para período invertido, retirada negativa e custo zero |
| `test_motor_de_analise.py` | Cada alerta do motor (mínimo, falta, vencimento, excesso, baixa movimentação, consumo incomum), a reposição estimada com as contas à mão, e as limitações quando falta histórico ou cadastro; retirada não sai de lote já vencido (só quando não há lote bom) e o descarte sai primeiro dele; custo médio ponderado pela quantidade (compra sem preço fora) e dinheiro no padrão brasileiro; valor em R$ no fim da justificativa do vencido, do vencimento próximo e do excesso (só o capital acima de 180 dias de consumo), e nenhum valor nos outros alertas; reposição em embalagens fechadas, com pedido mínimo antes do arredondamento e custo estimado; a limitação da reposição diz só o que falta (embalagem, preço) |

```bash
make test-backend                 # no container
cd backend && uv run pytest       # no host (exige uv)
uv run pytest tests/test_health.py -k ready -v
```

### Integração: API real + PostgreSQL real (`backend/tests/integracao/`)

A suíte acima usa SQLite e o `TestClient`. Esta sobe o **uvicorn de verdade** num processo à
parte, contra um **PostgreSQL de verdade** com o schema criado **pelas migrations** (não pelos
modelos), e os testes falam **HTTP** com ele, como o site e o app. Pega o que a outra não vê:
constraint do PostgreSQL, migration que diverge do modelo, serialização na rede.

Só roda com `INTEGRACAO_DATABASE_URL` apontando para um banco **descartável** (o schema `public`
é apagado e recriado no início); sem a variável, os testes são pulados. No CI, roda em todo PR
com um PostgreSQL de serviço.

| Arquivo | Cobre |
|---|---|
| `test_migracoes.py` | Todas as migrations descem até o zero e sobem de novo; `alembic check` sem diferença entre migrations e modelos; o downgrade da 0006 se recusa a descartar preços e embalagens sem `-x descartar_precos=sim`, o da 0007 os uuids do app sem `-x descartar_uuids=sim`, o da 0008 os talhões e as carências sem `-x descartar_talhoes=sim`, e o da 0009 os usuários sem `-x descartar_usuarios=sim`; o banco recusa login fora de minúsculas e papel desconhecido, e o usuário que lançou não se apaga nem fora da API; o banco recusa o mesmo uuid duas vezes; o banco recusa movimentação incoerente mesmo inserida fora da API (inclusive preço em saída, em ajuste de inventário e preço zero), talhão em entrada, descarte e ajuste de inventário, e o talhão com aplicação não se apaga nem fora da API |
| `test_fluxo_lotes_descarte_inventario.py` | O produtor com um lote vencido na prateleira: o alerta mostra o vencido inteiro, o descarte o tira sem mexer no consumo, a contagem do galpão lança a falta, o relatório leva tudo e volta pela importação; restauração da cópia de segurança num banco vazio refaz estoque e análise iguais; erros de uso com o status certo |
| `test_fluxo_sincronizacao.py` | O produtor que lança no campo, sem sinal: a fila em lote; a resposta se perde e o mesmo lote volta (tudo `ja_existia`, estoque e análise iguais); um item com a quantidade digitada errada no meio (os outros gravam); oito envios **simultâneos** do mesmo lançamento e seis do mesmo lote, em threads contra o uvicorn (uma linha por uuid, nenhum `500`); POST simples repetido (`200`, com as casas que o PostgreSQL guardou) e com outro conteúdo (`409`); avisos de estoque negativo, de data atrasada e de lançamento feito no site e no app; relatório sem o uuid e restauração da cópia de segurança com o mesmo estoque |
| `test_fluxo_talhoes.py` | O produtor que diz onde aplicou: talhões e defensivos com carência e preço, aplicações pelo POST e pela fila do app (reenviada sem duplicar), o talhão em carência com a data e a conta (vale a carência que acaba por último), custo total e por hectare, recorte da safra, talhão com aplicação recusando a remoção (`409`), relatório com a aba Talhões; a cópia de segurança num banco vazio diz quais talhões faltam e, com eles cadastrados, devolve cada aplicação ao seu talhão com a mesma carência e o mesmo custo; erros de uso `422` |
| `test_numeros_como_o_banco_guarda.py` | Achados da revisão de código que só o PostgreSQL mostra: o reenvio idêntico de 1,2345 kg e R$ 0,01235 continua sendo o mesmo lançamento (o banco arredonda o meio para longe do zero, o `round()` do Python não); item que o banco zeraria (0,0001 kg) volta `recusada` sem derrubar o lote nem travar o reenvio; preço, embalagem e área que virariam zero dão `422`; nome repetido continua `409` |
| `test_entradas_que_o_postgres_recusa.py` | Caractere nulo no login responde como login inexistente (`401`, e não `500` numa rota pública); id maior que o `integer` do PostgreSQL na URL, na query e no lote do app não vira `500` |
| `test_fluxo_autenticacao.py` | Contra um segundo uvicorn, no mesmo banco, com `AUTENTICACAO=true` (os outros arquivos usam o de `AUTENTICACAO=false`). O dono criado pelo **comando de verdade** (`python -m app.usuarios criar-dono`, em subprocesso, senha por variável de ambiente; o segundo é recusado sem `--outro-dono`) entra e cadastra o funcionário; o funcionário lança pelo POST e pela fila do app (o autor gravado no PostgreSQL) e leva `403` ao apagar, importar, baixar o relatório, cadastrar insumo e gerir usuários; sem token e com token falso, `401`; sair encerra só aquela sessão; trocar a senha encerra as outras; a sessão vencida no PostgreSQL não vale; desativado, o token cai na hora; o último dono não sai. **Bloqueio:** 5 senhas erradas e a sexta, certa, recusada com a resposta de um login inexistente, bloqueio de 15 minutos no banco, desfeito pela senha redefinida; dez chutes **simultâneos** em threads terminam bloqueados (a trava na linha do usuário). A API em `production` sem `AUTENTICACAO=true` (ausente ou `false`) **não sobe**; com ela, sobe sem `/docs` e com `401` |
| `test_fluxo_precos.py` | O produtor que anota preços: ureia com saco de 50 kg e pedido mínimo, compras a preços diferentes, custo médio e valor em estoque, alerta de vencido e de excesso em reais, reposição em sacos fechados com custo; descarte e falta da contagem como perda no `GET /resumo` e no relatório; a cópia de segurança restaurada num banco vazio devolve os preços e, relançado o cadastro, a mesma análise; preço em saída, em descarte, negativo ou zero e embalagem zero são `422`, e preço numa saída da planilha é erro na linha |

```bash
make test-integracao              # com o `make up` rodando (banco campocerto_teste à parte)

# no host, com um PostgreSQL descartável:
docker run --rm -d --name cc-integracao -e POSTGRES_PASSWORD=teste -e POSTGRES_DB=cc   -p 127.0.0.1:55432:5432 postgres:18-alpine
cd backend && INTEGRACAO_DATABASE_URL=postgresql+psycopg://postgres:teste@127.0.0.1:55432/cc   uv run pytest tests/integracao
```

**Regras:** regra de domínio e análise são testadas sem banco, com dados construídos no próprio
teste. Nada de dado real do desafio em fixture: sintético, sempre. Teste não acessa a internet.

## Frontend: Vitest (`frontend/tests/unit/`)

Ambiente `jsdom`, configurado em `vite.config.ts`. Os serviços HTTP são substituídos por
`vi.mock`, sem rede.

| Arquivo | Cobre |
|---|---|
| `navegacao.spec.ts` | Cada rota renderiza a sua página (inclusive 404); menu lista as telas na ordem; barra de baixo do celular com as mesmas telas, rótulos curtos, aba acesa e número de urgentes; tocar na aba atual sobe ao topo sem navegar; na página de um insumo, a aba Insumos leva de volta à lista; resumo de status no menu |
| `estoque.spec.ts` | Store: alertas de todos os insumos, os mais graves primeiro; recarga após lançar movimentação; mensagem legível sem API. Painel: alertas com justificativa, reposição, lista de compras do WhatsApp ("Pedir agora" separado dos próximos), cartões de gravidade que filtram a lista, barras de cobertura (falta, pedir hoje, folga) em ordem, estado vazio |
| `importacao.spec.ts` | Tela de importação: CSV decodificado do Windows-1252, `.xlsx` enviado em base64, `.xls`, `.ods`, `.numbers` e formato desconhecido barrados com a instrução do que fazer; mostra o resumo e os totais, só grava ao confirmar e recarrega o estoque; com erros, lista-os e não oferece importar; se o confirmar falha, não oferece o mesmo botão e confere de novo; o link do modelo aponta para a planilha da API |
| `insumo.spec.ts` | Página do insumo: resumo, alertas sem repetir o nome, "Insumos" aceso no menu, alertas mesmo sem movimentação, remover e voltar à lista. Gráfico (ECharts substituído por um mock que guarda a configuração): saldo mantido até hoje, projeção com a mesma cobertura do cartão, texto do usuário escapado no tooltip |
| `movimentacoes.spec.ts` | Movimentações no celular: extrato agrupado por dia ("Hoje", "Ontem", dia da semana) com sinal e unidade; confirmação em palavras do que acabou de ser lançado |
| `statusSistema.spec.ts` | Store: API e banco ok; banco indisponível; API fora do ar não afirma nada sobre o banco; getter `situacao` |
| `IndicadorDeStatus.spec.ts` | Componente mostra o texto de cada estado |

```bash
make test-frontend                # no container
cd frontend && npm test           # no host (exige Node 24)
```

## App: flutter test (`mobile/test/`)

Sem celular nem emulador. A API é substituída por um `MockClient` do pacote `http`, que responde
no formato da API de verdade (`test/dados.dart`).

| Arquivo | Cobre |
|---|---|
| `api_test.dart` | Modelos leem o JSON da API e mandam datas em AAAA-MM-DD; o `ClienteApi` usa a frase da API no erro, trata "sem resposta" e aceita o 503 do `/ready`; acentos em UTF-8; formatação brasileira de quantidade e data |
| `app_test.dart` | O app inteiro: Painel com alertas e justificativa, Insumos com separador de milhar, Movimentações com o nome do insumo, Sistema, e o aviso com "Tentar de novo" sem API |

```bash
cd mobile && flutter analyze && flutter test   # exige Flutter 3.47.7
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

`.github/workflows/verificacao.yml` roda o mesmo que o `make verify` (ruff, pytest, vue-tsc,
eslint e vitest), mais `dart format`, `flutter analyze` e `flutter test` do app, em todo PR e
em todo push na `main`, direto com uv, Node e Flutter (sem Docker). PR com a verificação
vermelha não deve ser mergeado.

## Lint e tipos

```bash
make lint      # ruff check + ruff format --check + vue-tsc + eslint
make verify    # lint + todos os testes, rodar antes de commitar
```
