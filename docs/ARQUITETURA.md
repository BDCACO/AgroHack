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
| `app/core/senha.py` | Hash Argon2id da senha (`argon2-cffi`), com o sal e os parâmetros gravados junto; confere também as senhas antigas em scrypt |
| `app/api/router.py` | Agrega as rotas da v1 (`/api/v1`), cada grupo com o seu nível de permissão |
| `app/api/permissoes.py` | As dependências de cada nível (sessão, funcionário, dono) e quem fez o pedido |
| `app/api/routes/` | Rotas HTTP, finas: validam entrada, chamam serviço, devolvem schema |
| `app/schemas/` | Modelos Pydantic de entrada/saída da API |
| `app/models/` | Modelos ORM (SQLAlchemy). Todo modelo novo é importado em `models/__init__.py` |
| `migrations/` | Alembic. Linhagem única, toda migration com `downgrade` |
| `tests/` | Pytest |

### Domínio e análise (motor de análise)

| Caminho | Responsabilidade | Regra |
|---|---|---|
| `app/domain/estoque.py` | Tipos de entrada (`Insumo`, `Lote`, `Retirada`, `Entrada`), `Alerta` e as regras que não dependem de histórico: estoque abaixo do mínimo, lote vencido ou a vencer, custo médio das compras; e a formatação brasileira de quantidade e dinheiro | **Sem I/O, sem banco, sem `datetime.now()`**: a data de referência entra como parâmetro |
| `app/domain/talhao.py` | A carência do talhão (quando a colheita fica liberada, o alerta com a conta e o que não se sabe) e o custo do que foi aplicado nele, total, por hectare e por insumo, num período | As mesmas: data de referência e período por parâmetro |
| `app/analysis/consumo.py` | `analisar(...)`: consumo médio, cobertura em dias, risco de falta, excesso, baixa movimentação, consumo incomum e reposição estimada (em embalagens fechadas, com pedido mínimo e custo, quando cadastrados, e descontado o que já foi pedido e não chegou, `a_caminho`) | Recebe listas, devolve `Analise` com **justificativa** em cada alerta e as **limitações** dos dados |

Os limiares (janela de 90 dias, 30 dias para vencimento, 180 de cobertura para excesso, prazo
padrão de 15 dias...) são constantes no topo de cada módulo, com o porquê ao lado. A análise usa
`statistics` da biblioteca padrão, não Pandas: média e desvio de uma lista de retiradas não
pedem DataFrame, e a conta fica legível para quem vai justificá-la ao produtor. A importação de
planilhas também não pediu: o `csv` da biblioteca padrão lê o CSV.

A resposta das rotas é o próprio `Analise` do motor (dataclass), sem schema espelho.

### Estoque (banco, serviço e rotas)

| Caminho | Responsabilidade |
|---|---|
| `app/models/estoque.py` | `insumos` (com `embalagem`, `pedido_minimo` e `carencia_dias` opcionais), `talhoes` (nome, `area_ha`, `cultura`) e `movimentacoes` (entrada ou saída, data, quantidade, validade, `motivo`: vazio, `descarte` ou `inventario`, `valor_unitario`, o preço da compra, `uuid`, o identificador gerado pelo app, `talhao_id`, onde a retirada foi aplicada, `usuario_id`, quem lançou, `fornecedor_id`, de quem foi a compra, e `item_do_pedido_id`, o pedido que a entrada recebeu). **O estoque atual não é coluna**: é a soma das movimentações, calculada na leitura. Uma fonte da verdade só. O custo médio também não: sai das compras |
| `app/services/estoque.py` | Casos de uso: cadastro, movimentações, a análise de cada insumo a partir do banco e o saldo dia a dia (histórico do gráfico). As rotas falam só com os serviços (este, `importacao`, `planilha_modelo` e `relatorio`) |
| `app/services/importacao.py` | Importação de movimentações por planilha (Excel ou CSV), ver abaixo |
| `app/services/planilha_modelo.py` | A planilha modelo da importação e os estilos das planilhas geradas (cores da marca, títulos, impressão) |
| `app/services/relatorio.py` | O relatório em Excel: resumo (com os totais em reais), alertas, reposição, situação de cada insumo, talhões (carência e custo) e todas as movimentações |
| `app/services/talhoes.py` | Cadastro de talhões e a leitura de cada um: carência e custo calculados das aplicações, com o custo médio pela mesma regra da tela do insumo |
| `app/services/sincronizacao.py` | A fila de lançamentos do app (`POST /movimentacoes/lote`): grava item a item, traduz os erros de validação em frases e calcula os avisos (ver abaixo) |
| `app/services/resumo.py` | A visão geral em reais (`GET /resumo`): soma o que `estoque.listar_insumos` já analisou, mais as perdas |
| `app/models/compras.py` | `fornecedores` (nome único, contato, telefone, cidade, observação, `ativo`), `pedidos` (fornecedor, `situacao`, `feito_em`, `previsto_para`, observação, quem fez) e `itens_do_pedido` (insumo, quantidade, preço combinado, `quantidade_recebida`) |
| `app/services/fornecedores.py` | Cadastro dos fornecedores e o detalhe com as compras recentes e o preço médio pago por insumo |
| `app/services/pedidos.py` | Pedidos de compra: fazer, alterar, cancelar e receber (a carga vira as entradas); a situação pelo que já chegou |
| `app/services/sugestao_de_pedido.py` | O pedido sugerido: as reposições do motor, agrupadas pelo fornecedor da última compra, com o preço dela |
| `app/models/usuario.py` | `usuarios` (login em minúsculas, hash da senha, papel, ativo, falhas seguidas e bloqueio) e `sessoes` (o SHA-256 do token, validade, encerramento, aparelho) |
| `app/services/autenticacao.py` | Login, a sessão conferida a cada pedido, sair, trocar a senha e o bloqueio por senhas erradas |
| `app/services/usuarios.py` | Gestão pelo dono: cadastrar, alterar, desativar, redefinir a senha; o último dono ativo |
| `app/usuarios.py` | O comando que cria o primeiro dono no servidor (`make usuario-dono`) |
| `app/demo.py` | Fazenda fictícia para a apresentação (`make demo`): insumos e talhões marcados com `demonstracao`, que a tela sinaliza e `make demo-limpar` apaga sozinhos (menos o talhão em que se lançou a aplicação de um insumo real) |
| `app/core/relogio.py` | `hoje()` na data de Rondônia (UTC−4 fixo, sem horário de verão), não na do servidor |

Lote = entrada com validade. Como a retirada não diz de qual lote saiu, o saldo de cada lote é
estimado supondo que se usa primeiro o que vence primeiro (`lotes_em_estoque`), e a análise diz
isso nas limitações. Lote que já tinha vencido na data da retirada fica por último: ninguém
aplica produto vencido, e ele segue no alerta até ser **descartado**. Quantidades são
`NUMERIC(12, 3)` no banco e `float` no Python.

**Saída que não é consumo.** A coluna `motivo` separa a retirada para uso (sem motivo) do
**descarte** (lote vencido ou produto estragado, jogado fora ou devolvido; sai primeiro do
vencido) e do **ajuste de inventário** (a diferença entre a contagem do galpão e o saldo
registrado; entrada se sobrou, saída se faltou). Os dois tiram ou põem no estoque, mas não
entram no ritmo de consumo nem nos alertas de consumo. É uma coluna à parte, e não um terceiro
`tipo`: para o saldo, o site e o app, continuam sendo entrada ou saída.

**Preço, embalagem e pedido mínimo (opcionais).** A compra pode trazer `valor_unitario` (R$
por unidade do insumo, `NUMERIC(14, 4)`: o preço por mililitro de um defensivo tem centavos
depois da vírgula). Só em compra: o banco recusa preço em saída, em ajuste de inventário e
preço zero ou negativo. Sem preço nenhum, tudo funciona como antes; com ele:

- **Custo médio** (`custo_medio`, no domínio): média do preço pago **ponderada pela
  quantidade** das compras com preço. Compra sem preço fica fora da conta, e a análise diz
  quantas ficaram; a sobra de inventário não é compra. Sem compra com preço, é `None`, e não
  zero.
- **Alertas em reais.** Lote vencido ou a vencer vale quantidade do lote × custo médio; o
  excesso vale só o capital de fato parado, o que passa de 180 dias de consumo. O valor vai no
  campo `valor` do alerta e numa frase no **fim** da justificativa, com o custo usado ("Pelo
  custo médio de R$ 3,30/kg, são cerca de R$ 950,00."). O começo do texto não muda: a tela se
  apoia nele. Os outros alertas não têm valor.
- **Reposição.** A quantidade da conta sobe ao `pedido_minimo` e é arredondada para cima ao
  múltiplo da `embalagem` (do insumo, na unidade dele: 50 para o saco de 50 kg); a
  justificativa fala em embalagens e diz quanto a conta dava. Com custo médio, traz
  `custo_estimado`. A limitação sobre o que a sugestão não considera diz só o que falta
  (embalagem, preço) e some com os dois cadastrados; pedido mínimo vazio é fornecedor sem
  mínimo, não falta de dado. `Reposicao.quantidade` virou número com casas, porque a
  embalagem pode ser fracionada (frasco de 0,5 L).
- **Compatibilidade.** Tudo é aditivo: campos novos nas respostas, opcionais nos pedidos.
  `PUT /insumos/{id}` sem `embalagem` ou `pedido_minimo` mantém o que está gravado (o site e o
  app de antes não conhecem esses campos e apagariam o que outro cadastrou); mandar `null` de
  propósito limpa.
- **Migration 0006.** O downgrade apagaria preços e embalagens, que a 0005 não tem onde
  guardar: ele se recusa enquanto houver algum gravado, e só segue com
  `alembic -x descartar_precos=sim downgrade 0005` (antes, baixe o relatório, que leva os
  preços).

### Talhões e carência

Para onde foi cada retirada: com isso, o custo por talhão e por hectare e o aviso do **prazo de
carência** (os dias mínimos entre aplicar um defensivo e colher ou abater), que é segurança do
alimento, exigência legal e motivo de carga recusada. Decisões:

- **Talhão** (`talhoes`): nome único, `area_ha` (`NUMERIC(10, 2)`, maior que zero, porque é o
  divisor do custo por hectare) e `cultura` opcional ("Soja", "Pasto"). Talhão não nasce da
  planilha, ao contrário do insumo: falta a área.
- **Aplicação = retirada para uso com `talhao_id`.** Não é um terceiro `tipo` nem um `motivo`:
  para o saldo, o consumo, o site e o app continua sendo uma saída. Só ela tem talhão: o schema
  recusa em entrada e em descarte com a frase do porquê, e o banco tem a mesma regra
  (`ck_movimentacoes_talhao_so_em_aplicacao`), inclusive para o ajuste de inventário. Talhão
  inexistente é `422`, como o insumo inexistente; no lote do app, `recusada` com a frase.
- **Rastreabilidade não se perde.** A FK é `RESTRICT`, e `DELETE /talhoes/{id}` com aplicação é
  `409` dizendo quantas. Remover o **insumo** continua levando as movimentações dele (regra de
  antes), e com elas as aplicações.
- **Carência no insumo** (`carencia_dias`, 0 a 365, opcional): 0 é "não tem carência" (a ureia);
  vazio é "não informada". Como a embalagem, o `PUT` sem o campo mantém o gravado. Fica fora do
  motor de análise e do `POST /analises`: é regra do talhão.
- **Quando libera:** o maior `data + carência` entre as aplicações com carência, e não o da
  aplicação mais recente (um inseticida de 30 dias aplicado há 10 prende mais que um fungicida de
  3 dias aplicado ontem). No próprio dia da liberação já pode colher. A justificativa diz o
  talhão, a data, quantos dias faltam, o insumo que prende, quando foi aplicado e a carência:
  "Talhão Norte: não colher nem abater antes de 12/11/2026 (faltam 9 dias). Fungicida X aplicado
  em 28/10/2026, carência de 15 dias."
- **Gravidade sempre alta enquanto em carência.** Colher antes é proibido, e o erro não tem
  conserto (resíduo no alimento, carga recusada, multa). Não há meio-termo entre proibido e
  permitido, e não se sabe quando o produtor pretende colher, então a distância até a liberação
  não diminui o risco. Liberado, não há alerta.
- **O que não se sabe vira limitação:** insumo aplicado sem carência cadastrada (não dá para
  saber se é defensivo), com os nomes e o pedido de cadastrar (0 se não tem); e que a carência é
  a do cadastro, a conferir na bula ou no receituário, porque muda com a cultura.
- **Custo:** quantidade aplicada × custo médio do insumo (o mesmo do estoque e das perdas),
  somado por insumo e no talhão, e dividido pela área. Limitações: é o custo médio de hoje, não o
  preço da época; aplicação de insumo sem preço fica fora, e a limitação diz quantas. Com
  aplicação e nenhuma com preço, o custo é `null`, e não zero.
- **Período** (`desde` e `ate`, opcionais e inclusive): recorta uma safra no custo, no consumo e
  na lista de aplicações. A carência olha **todas** as aplicações: um defensivo aplicado antes do
  recorte continua proibindo a colheita.
- **Resumo:** `GET /resumo` ganha `talhoes_em_carencia`. Os `alertas` por gravidade continuam
  sendo só os dos insumos, de propósito: o Painel mostra esses números ao lado da lista de
  alertas dos insumos, e um urgente a mais sem o cartão correspondente confundiria. Pelo mesmo
  motivo, a aba Alertas do relatório é só dos insumos, e a carência aparece na aba Talhões.
- **Planilha:** coluna opcional `talhao` (só em saída para uso; o talhão tem de estar cadastrado,
  casado sem diferenciar maiúsculas). O relatório escreve o talhão de cada aplicação, e a cópia de
  segurança volta igual; num banco vazio, os talhões precisam ser cadastrados antes (a importação
  diz quais faltam, e a aba Talhões do relatório tem a área e a cultura). Criá-los a partir dessa
  aba seria uma segunda regra de importação, escondida, para um caso raro.
- **Migration 0008.** O downgrade apagaria talhões, aplicações e carências: ele se recusa
  enquanto houver algum talhão ou carência cadastrada, e só segue com
  `alembic -x descartar_talhoes=sim downgrade 0007`.

### Fornecedores e pedidos de compra

A análise já dizia "pedir 14 sacos de ureia", mas o ciclo parava aí: o produtor pedia por
telefone, e no dia seguinte o sistema mandava pedir de novo o que estava a caminho. Agora o
ciclo fecha: **sugerido → pedido → recebido**, e o recebimento vira a entrada no estoque.
Decisões:

- **Fornecedor** (`fornecedores`): nome único (`409`), contato, telefone (o WhatsApp da
  revenda), cidade e observação opcionais; o campo apagado na tela ("") vira vazio. O `PUT`
  muda só o que veio: desativar não apaga o telefone.
- **Remover só sem história.** Com compra ou pedido registrado, `DELETE` é `409`, pedindo
  para desativar (`ativo: false`): apagar levaria de quem foi cada compra e o preço pago a
  ele, que é o que permite comparar revendas. As FKs são `RESTRICT`. O desativado sai das
  escolhas (o pedido a ele é `422`, e a sugestão não o usa), mas a compra com ele continua
  aceita: pode ser antiga, e a cópia de segurança precisa voltar.
- **De quem se comprou** (`movimentacoes.fornecedor_id`): opcional, só na compra (entrada
  sem motivo), com o CHECK `ck_movimentacoes_fornecedor_so_em_compra` e a frase no schema;
  no `POST`, na fila do app (inexistente é `recusada`) e na resposta, com `comprado_de` (o
  nome, como o `lancado_por`). O reenvio de um uuid com outro fornecedor é `409`.
- **Preço por fornecedor**: o detalhe do fornecedor traz as compras recentes (20) e, por
  insumo, o preço médio pago a ele (pela regra do custo médio: ponderado pela quantidade, só
  as compras com preço), o último preço e a última compra; o detalhe do insumo traz
  `precos_por_fornecedor`, o mais barato primeiro.
- **Pedido** (`pedidos` + `itens_do_pedido`): fornecedor opcional (o pedido por telefone a
  quem não está cadastrado vale), `feito_em` (padrão hoje, não futura), `previsto_para`
  (opcional, não antes do pedido) e uma linha por insumo (o recebimento aponta para ela sem
  ambiguidade). `situacao`: `aberto`, `parcial`, `recebido` ou `cancelado`. A resposta traz o
  que falta de cada linha, o custo pelos preços combinados e `atrasado` (a previsão passou
  e falta chegar).
- **Alterar só o aberto**, antes de chegar qualquer coisa (`409` depois): as entradas já
  gravadas apontam para as linhas, e mudar o pedido as deixaria contando outra história. A
  linha do mesmo insumo continua a mesma, com a quantidade nova.
- **Cancelar** não desfaz o que chegou (está no galpão); o que faltava não vem mais. O
  pedido que chegou inteiro não se cancela (`409`); cancelar de novo não muda nada.
- **Receber** (`POST /pedidos/{id}/receber`): a data da chegada (padrão hoje, nem futura nem
  antes do pedido) e, por linha, a quantidade, a validade do lote e o preço se a nota veio
  com outro. Cada linha vira uma entrada com o fornecedor do pedido, o preço (o combinado
  ou o da nota), a validade, quem conferiu e `item_do_pedido_id`; a linha soma o recebido e
  o pedido passa a `parcial` ou `recebido`. Numa transação, com o pedido travado
  (`FOR UPDATE`): dois celulares recebendo a mesma carga entram um de cada vez.
- **A carga a mais entra, com aviso** ("confira a nota"), em vez de ser recusada: o que
  chegou está no galpão, e recusar deixaria o estoque menor que o real ou obrigaria a
  lançar a sobra à parte, sem fornecedor. `quantidade_recebida` pode passar da quantidade;
  o que falta nunca fica negativo.
- **Remover a entrada recebida** (digitada errado) devolve a quantidade à linha, e o pedido
  volta a parcial ou aberto, na mesma transação. `quantidade_recebida` é coluna, e não a
  soma das entradas, porque a situação do pedido também é guardada (o filtro por situação
  é uma consulta simples); os dois mudam juntos no recebimento e na remoção.
- **O motor sabe do que já foi pedido** (`analisar(..., a_caminho=[Encomenda(...)])`, puro,
  opcional). A **reposição** conta o que falta chegar dos pedidos abertos e parciais como se
  estivesse no galpão (a posição de estoque) e diz isso na justificativa ("Desconta os 950
  kg já pedidos e ainda não recebidos."): não manda comprar de novo. O **alerta de risco de
  falta** continua aparecendo, porque o estoque físico continua baixo, e diz quanto foi
  pedido e quando chega; ele só deixa de ser urgente (vira atenção) se o pedido chega antes
  de o estoque acabar e, com ele, o estoque passa do prazo de reposição. Entrega atrasada
  (previsão vencida), que chega depois de acabar ou sem data continua urgente; o pedido sem
  data vira limitação. O insumo ganha `em_pedido` e `chegada_prevista` (aditivos), e o
  `POST /analises` aceita `a_caminho`, opcional.
- **Pedido sugerido** (`GET /pedidos/sugestao?dias=7`): as reposições para pedir hoje ou nos
  próximos dias, agrupadas pelo fornecedor da última compra de cada insumo (o sem fornecedor
  por último), com a quantidade da reposição e o preço da última compra, que é o que a
  revenda cobra hoje (sem ele, o custo médio). Cada grupo vai como está para
  `POST /pedidos`; o que já foi pedido sai da sugestão.
- **Remover o insumo** leva as linhas de pedido dele (CASCADE, como as movimentações), e o
  pedido que fica vazio sai junto.
- **Planilha**: coluna opcional `fornecedor`, só em compra. O fornecedor que não existe é
  **cadastrado pelo nome**, como o insumo novo, e não recusado como o talhão: o talhão
  precisa da área, o fornecedor só do nome, e a cópia de segurança restaurada num sistema
  vazio traz de volta de quem foi cada compra sem cadastro à mão. A prévia lista
  `fornecedores_novos`, para conferir a grafia. `ja_lancadas` trata o fornecedor como o
  preço e o talhão. O relatório escreve o fornecedor de cada compra na aba Movimentações e
  ganha a aba **Pedidos** (o que falta chegar dos abertos e parciais, com a previsão e o
  atrasado em destaque), que não volta pela importação.
- **Permissões**: ler fornecedores, pedidos e a sugestão, e **receber** a carga, é do
  funcionário (é ele quem confere no galpão o que chegou); cadastrar fornecedor e fazer,
  alterar ou cancelar pedido é do dono, que compra e paga. O preço pago a cada revenda não
  ficou só com o dono: o funcionário já lê o custo médio e o preço de cada compra, e
  esconder o preço por fornecedor pediria um schema por papel sem proteger nada que ele já
  não veja. O relatório, com todos os preços e a cópia de segurança, continua do dono.
- **Migration 0010.** O downgrade apagaria fornecedores, pedidos e de quem foi cada
  compra: ele se recusa enquanto houver algum fornecedor ou pedido, e só segue com
  `alembic -x descartar_compras=sim downgrade 0009`.

### Lançamento offline do app (sincronização)

No campo o sinal cai. O app guarda os lançamentos no celular e os manda quando a rede volta,
quantas vezes precisar, sem duplicar e sem perder nada. Decisões:

- **O identificador nasce no celular.** `movimentacoes.uuid` (`UUID`, opcional e `UNIQUE`) é
  gerado pelo app no momento do lançamento, antes de qualquer envio: é ele que diz ao servidor
  "este é o mesmo lançamento". Fica vazio no que vem do site, da importação e da contagem do
  galpão. Não vai para a planilha (é detalhe técnico): o relatório e a importação ignoram a
  coluna, e a cópia de segurança restaurada volta sem uuid.
- **`POST /movimentacoes` com `uuid` é idempotente.** Se o uuid já está gravado com o mesmo
  conteúdo (insumo, tipo, data, quantidade, validade, motivo e preço, comparados com as casas
  que o banco guarda), devolve o lançamento gravado com **`200`** em vez de `201` e não grava de
  novo. Com outro conteúdo, **`409`** dizendo quais campos diferem: é o app reaproveitando o
  identificador, e gravar ou ignorar perderia um dos dois em silêncio. Sem `uuid`, nada muda:
  duas retiradas iguais no mesmo dia continuam sendo duas.
- **Envio simultâneo.** O app pode reenviar enquanto o primeiro envio ainda grava. Os dois
  passam pela consulta antes de um deles gravar; quem barra o segundo é o `UNIQUE` do banco, e a
  violação (`IntegrityError`) vira o caso do reenvio (`200` ou `ja_existia`), não um `500`.
- **`POST /movimentacoes/lote`, item a item.** Até 500 lançamentos, na ordem da fila, cada um com
  `uuid` obrigatório e na **própria transação**. Não é tudo ou nada como a importação de
  planilha: a fila é do celular, e um item ruim não pode travar os que o produtor já fez. Os
  itens chegam como objetos genéricos e cada um é validado sozinho com o schema de sempre;
  item malformado (até um que nem é objeto) volta `recusada` com os erros em frases, com o nome
  do campo ("quantidade tem de ser maior que 0."), em vez de um `422` que derrubaria o lote. O
  pedido em si malformado (sem `movimentacoes`, mais de 500 itens) continua `422`. Se o envio
  cair no meio, o que já entrou fica, e o reenvio do lote o devolve como `ja_existia`. 500
  itens dão uns 100 kB, longe do limite de 8 MB do corpo.
- **Resposta do lote:** `resultados`, na ordem do envio, cada um com `uuid` (o enviado; `null`
  se não deu para ler), `situacao` (`gravada`, `ja_existia` ou `recusada`), `movimentacao`
  (quando gravada ou já existia), `erros` e `avisos`; e `resumo` com `gravadas`, `ja_existiam`
  e `recusadas`.
- **Avisos não impedem nada**, só pedem para conferir: (1) o estoque do insumo fica negativo
  depois do lote inteiro ("O estoque de Ureia fica em -2 kg com este envio: falta lançar uma
  entrada?"), uma vez por insumo, na última saída dele; o saldo é o do fim do lote porque a
  fila segue a ordem dos lançamentos, e uma entrada mais adiante pode cobrir a saída; (2) data
  de mais de 30 dias atrás (ano ou mês digitado errado, ou lançamento esquecido na fila); (3)
  o mesmo conteúdo já lançado **sem** uuid no mesmo dia: provavelmente digitado no site e no
  app. Voltam também no `ja_existia`, porque a primeira resposta pode ter se perdido. O `POST`
  simples não traz avisos: a resposta dele não mudou.
- **Remoção.** `DELETE /movimentacoes/{id}` continua igual e não deixa rastro: reenviar depois
  o mesmo uuid grava de novo. É a regra mais simples, e só acontece se o app reenviar algo que
  já tinha recebido resposta, o que ele não faz (seção 4). Guardar os uuids removidos
  protegeria contra isso, mas é mais uma tabela e mais uma regra para explicar ao produtor.
- **Migration 0007.** O downgrade apagaria os uuids, e um lançamento ainda na fila de algum
  celular seria gravado de novo depois: ele se recusa enquanto houver algum gravado, e só segue
  com `alembic -x descartar_uuids=sim downgrade 0006` (com os celulares já sincronizados).

### Autenticação e papéis

Até aqui, qualquer um que alcançasse a tela lia, alterava e apagava tudo. Agora há login, com
dois papéis: o **dono** e o **funcionário** (o peão que lança no campo). Decisões:

- **Liga e desliga, fail-closed em produção.** `AUTENTICACAO=true|false`. Em `production`, a API
  **não sobe** sem `AUTENTICACAO=true` (como o `ENVIRONMENT` inválido): esquecer a variável não
  pode deixar a produção aberta. Em `development` e `test` o padrão é desligada, para o site e o
  app, que ainda não têm tela de login, continuarem funcionando; ao subir assim, a API avisa no
  log.
- **Desligada**, pedido sem token passa como antes, com os poderes do dono. Mas o token enviado
  vale: válido, o usuário é reconhecido (vai para a auditoria) e o papel dele conta (funcionário
  em rota do dono é `403`); falso, vencido ou encerrado é `401`. Assim o site e o app implementam
  o login contra a API de desenvolvimento sem precisar ligá-la. As rotas da própria sessão e a
  gestão de usuários exigem login **sempre**: desligada, sem isso, qualquer um na rede criaria
  um dono para si.
- **Senha:** **Argon2id** (`argon2-cffi`), a primeira escolha da OWASP para senhas, no
  perfil de baixa memória da RFC 9106: 64 MiB, 3 passadas, paralelismo 4 (uns 0,1 s por
  tentativa), sal aleatório por senha, gravado como `$argon2id$v=19$m=…,t=…,p=…$sal$hash`.
  Com os parâmetros no hash, o custo pode subir depois, e o login refaz o hash de quem
  entrar. As senhas gravadas antes em scrypt (`scrypt$n$r$p$sal$hash`) seguem conferindo e
  viram Argon2id no próximo login: ninguém fica trancado pela troca de algoritmo. Comparação com `hmac.compare_digest`, acento normalizado (NFC),
  mínimo de 8 caracteres. Usuário não se apaga, **desativa**: as movimentações dizem quem as
  lançou.
- **Login** sem diferenciar maiúsculas: guardado em minúsculas (o banco confere com
  `login = lower(login)`), com o `UNIQUE` simples. Só letras sem acento, números, ponto, hífen
  e sublinhado: "zé" num teclado sem acento seria outro login.
- **Token opaco, e não JWT.** `secrets.token_urlsafe(32)`, devolvido **uma vez** no login; o
  banco guarda só o SHA-256 (sem sal nem Argon2id: são 256 bits aleatórios, e a conferência de
  cada pedido precisa ser rápida). O servidor procura a sessão a cada pedido, então sair,
  trocar a senha e desativar o usuário valem **na hora**, sem lista de revogação. Vai no
  cabeçalho `Authorization: Bearer <token>`.
- **Validade de 30 dias**, fixa, conferida a cada pedido. O app passa dias no campo sem sinal,
  lançando na fila, e um login vencido no meio da lida obrigaria o funcionário a achar sinal e
  lembrar a senha só para continuar. O risco do prazo longo (celular perdido) se resolve pelo
  dono, que desativa o usuário ou redefine a senha: as sessões dele caem na hora.
- **Respostas:** `401` com `WWW-Authenticate: Bearer` e a frase do motivo (falta o login,
  sessão inválida, encerrada, vencida, usuário desativado); `403` quando o papel não permite
  ("Só o dono da fazenda pode fazer isto: peça a ele.").
- **Contra adivinhação de senha:** 5 erros seguidos bloqueiam o login daquele usuário por 15
  minutos; o acerto zera a conta; tentar durante o bloqueio não o estende. Fica no banco
  (sobrevive a reiniciar e vale para todos os processos), com `FOR UPDATE` na linha do usuário:
  dez chutes simultâneos entram um de cada vez e não passam todos antes de o primeiro contar.
  A senha atual errada em `PUT /auth/senha` também conta. A resposta é **sempre a mesma**
  ("Login ou senha incorretos.", com a regra do bloqueio), para login inexistente, senha
  errada, usuário desativado e login bloqueado, e o login inexistente gasta o mesmo hash lento:
  nem o texto nem o tempo contam que o login existe. O dono vê `bloqueado_ate` em
  `GET /usuarios`, e redefinir a senha desbloqueia.
- **O último dono ativo** não se desativa nem vira funcionário (`409`), com `FOR UPDATE` nos
  donos para dois não se desativarem ao mesmo tempo.
- **Primeiro dono pelo servidor:** `python -m app.usuarios criar-dono --login ... --nome ...`
  (`make usuario-dono`), com a senha do terminal (`getpass`, duas vezes) ou de `SENHA_DO_DONO`
  para automação, nunca por argumento. Recusa se já houver dono ativo, a não ser com
  `--outro-dono` (a saída de quem tem o servidor e perdeu o acesso do dono). **Não há endpoint
  de "primeiro acesso"**: aberto na rede, quem chegasse antes do dono viraria o dono.
- **Auditoria:** o POST de movimentação, a fila do app, a contagem do galpão e a importação
  gravam `movimentacoes.usuario_id` (FK `RESTRICT`) de quem está logado, nunca de quem o corpo
  diz ser; a resposta traz `usuario_id` e `lancado_por` (o nome), aditivos. O reenvio de um
  uuid mantém quem lançou primeiro. Sem login, os dois vêm `null`, como no que foi lançado
  antes. O relatório e a planilha não levam o autor: a aba Movimentações é o formato da
  importação.
- **As permissões ficam no `include_router`** (`app/api/router.py`), e não rota a rota: as rotas
  de estoque e de talhões se dividem em `campo` e `gestao`. `tests/test_permissoes.py` percorre
  todas as rotas do app e exige que cada uma esteja na matriz abaixo: rota nova não nasce aberta
  por esquecimento.
- **Migration 0009.** O downgrade apagaria os usuários e o registro de quem lançou: ele se
  recusa enquanto houver usuário, e só segue com `alembic -x descartar_usuarios=sim downgrade
  0008`.

**Matriz de permissões** (com a autenticação ligada; desligada, ver acima):

| Nível | Quem | Rotas |
|---|---|---|
| Pública | qualquer um | `GET /health`, `GET /ready`, `/docs` e `/openapi.json` (fora de produção), `POST /auth/entrar` |
| Sessão | qualquer usuário logado, sobre si | `POST /auth/sair`, `GET /auth/eu`, `PUT /auth/senha` (exigem login mesmo desligada) |
| Funcionário | funcionário e dono | `GET /insumos`, `GET /insumos/{id}`, `GET /movimentacoes`, `GET /talhoes`, `GET /talhoes/{id}`, `GET /resumo`, `GET /fornecedores`, `GET /fornecedores/{id}`, `GET /pedidos`, `GET /pedidos/{id}`, `GET /pedidos/sugestao`; `POST /movimentacoes`, `POST /movimentacoes/lote`, `POST /insumos/{id}/inventario`, `POST /pedidos/{id}/receber` |
| Dono | só o dono | `POST`/`PUT`/`DELETE /insumos`, `DELETE /movimentacoes/{id}`, `POST`/`PUT`/`DELETE /talhoes`, `POST`/`PUT`/`DELETE /fornecedores`, `POST /pedidos`, `PUT /pedidos/{id}`, `POST /pedidos/{id}/cancelar`, `POST /importacoes`, `GET /importacoes/modelo.xlsx`, `GET /relatorio.xlsx`, `POST /analises` |
| Gestão | só o dono, sempre com login | `GET /usuarios`, `POST /usuarios`, `PUT /usuarios/{id}`, `PUT /usuarios/{id}/senha` |

O funcionário lê os insumos com o custo médio e o valor em estoque (as telas que ele usa são as
mesmas), e o preço pago a cada fornecedor; o relatório, com todos os preços e a cópia de
segurança, é só do dono. O funcionário recebe a carga de um pedido, mas não faz, altera nem
cancela pedido.

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
| `POST /api/v1/auth/entrar` | `{login, senha, dispositivo?}` → `{token, expira_em, usuario: {id, nome, login, papel}}`. O token vem uma vez só e vale 30 dias. Recusa sempre com o mesmo `401` |
| `POST /api/v1/auth/sair` · `GET /api/v1/auth/eu` | Encerra a sessão deste token (`204`) / quem está logado |
| `PUT /api/v1/auth/senha` | `{senha_atual, senha_nova}` (mínimo 8): troca a própria senha e encerra as sessões dos outros aparelhos (`204`); senha atual errada é `400` |
| `GET /api/v1/usuarios` · `POST /api/v1/usuarios` | Usuários com `ativo` e `bloqueado_ate` / cadastra (`nome`, `login`, `senha`, `papel`); login repetido `409` |
| `PUT /api/v1/usuarios/{id}` | `nome`, `papel`, `ativo` (o que não vier fica). Desativar derruba as sessões; o último dono ativo não sai (`409`) |
| `PUT /api/v1/usuarios/{id}/senha` | Redefine a senha (`senha_nova`), derruba as sessões e desfaz o bloqueio (`204`) |
| `GET /api/v1/ready` | Readiness: `200` com o banco respondendo, `503` sem ele |
| `GET /api/v1/insumos` | Insumos com estoque atual, `custo_medio`, `valor_em_estoque`, `em_pedido` e `chegada_prevista` (o que foi pedido e não chegou) e a análise de hoje (alertas com `valor` em R$, reposição com `custo_estimado` e descontado o que está a caminho, limitações) |
| `GET /api/v1/insumos/{id}` | Um insumo com a análise, o saldo no fim de cada dia com movimentação (`historico`), as movimentações e o preço médio pago a cada fornecedor (`precos_por_fornecedor`, o mais barato primeiro) |
| `POST /api/v1/insumos` · `PUT /api/v1/insumos/{id}` | Cadastra / altera insumo (nome, unidade, mínimo, prazo de reposição e, opcionais, `embalagem`, `pedido_minimo` e `carencia_dias`). `409` para nome repetido. No `PUT`, embalagem, pedido mínimo e carência ausentes ficam como estão |
| `DELETE /api/v1/insumos/{id}` | Remove o insumo cadastrado por engano, com as movimentações dele. `409` se ele foi aplicado em algum talhão: a rastreabilidade e a carência não somem com ele (remova antes as aplicações) |
| `GET /api/v1/movimentacoes` | Entradas e saídas, as mais recentes primeiro (`insumo_id`, `limite`), cada uma com `usuario_id` e `lancado_por` (quem lançou; `null` sem login), `fornecedor_id` e `comprado_de` (de quem foi a compra) e `item_do_pedido_id` (o pedido que ela recebeu) |
| `POST /api/v1/movimentacoes` | Lança entrada ou saída; saída com `motivo: "descarte"` não conta como consumo; entrada pode trazer `valor_unitario` (R$ por unidade); a compra pode trazer `fornecedor_id`; a retirada para uso pode trazer `talhao_id` (onde foi aplicada). `422` para data futura, validade ou preço em saída, preço zero ou negativo, descarte em entrada, talhão fora da retirada para uso, fornecedor fora da compra, insumo, talhão ou fornecedor inexistente. Com `uuid` (opcional, gerado pelo app), reenviar devolve o já gravado com `200`; o mesmo uuid com outro conteúdo é `409` |
| `POST /api/v1/movimentacoes/lote` | A fila do app: `{"movimentacoes": [...]}`, até 500, cada uma com `uuid`. Grava na ordem, item a item; devolve para cada uma `gravada`, `ja_existia` ou `recusada` (com os `erros` em frases) e os `avisos`, mais o `resumo`. Sempre `200`, a não ser que o pedido inteiro esteja malformado (`422`) |
| `POST /api/v1/insumos/{id}/inventario` | Contagem do galpão (`quantidade_contada`, `data` opcional): lança a diferença para o saldo registrado naquele dia como ajuste (`motivo: "inventario"`) e devolve saldo, contagem e diferença. Se bate, nada é lançado |
| `DELETE /api/v1/movimentacoes/{id}` | Remove lançamento errado (o mesmo uuid, reenviado depois, grava de novo). A entrada que recebeu um pedido devolve a quantidade a ele |
| `GET /api/v1/resumo` | Visão geral em reais: `valor_em_estoque` (`null` se nenhum insumo tem preço), `insumos_sem_preco`, `perdas` (descartes e faltas da contagem pelo custo médio: `ultimos_30_dias` e `total`), `compras_sugeridas` (custo das reposições dos próximos 30 dias, quantas e quantas para hoje), `alertas` por gravidade (só os dos insumos), `talhoes_em_carencia` e as `limitacoes` das somas |
| `GET /api/v1/talhoes` | Cada talhão com `area_ha`, `cultura`, `colheita_liberada_em`, `em_carencia`, o alerta de carência com a conta, `custo_total`, `custo_por_ha` e as `limitacoes`. `desde` e `ate` (opcionais) recortam o custo |
| `GET /api/v1/talhoes/{id}` | O mesmo, mais as `aplicacoes` do período (as mais recentes primeiro) e o `consumo` de cada insumo no talhão, com o custo |
| `POST /api/v1/talhoes` · `PUT /api/v1/talhoes/{id}` | Cadastra / altera talhão (nome, `area_ha` maior que zero, `cultura` opcional). `409` para nome repetido |
| `DELETE /api/v1/talhoes/{id}` | Remove o talhão sem aplicação; com alguma, `409` |
| `GET /api/v1/fornecedores` · `POST /api/v1/fornecedores` | Todos os fornecedores, com `ativo` / cadastra (`nome`; `contato`, `telefone`, `cidade`, `observacao` opcionais). `409` para nome repetido |
| `GET /api/v1/fornecedores/{id}` | O fornecedor, as 20 compras mais recentes e, por insumo, o preço médio pago a ele, o último preço e a última compra (`precos`) |
| `PUT /api/v1/fornecedores/{id}` · `DELETE /api/v1/fornecedores/{id}` | Altera só o que veio (`{"nome": ..., "ativo": false}` desativa) / remove o fornecedor sem compra nem pedido; com algum, `409` (desative-o) |
| `GET /api/v1/pedidos` | Pedidos, os mais recentes primeiro (`situacao`, `fornecedor_id`, `insumo_id`, `limite`), cada um com o fornecedor, quem fez, `atrasado`, `custo_estimado` e as linhas com `quantidade_recebida` e `falta_receber` |
| `GET /api/v1/pedidos/sugestao` | O pedido sugerido: as reposições para pedir hoje ou nos próximos `dias` (padrão 7, até 90), por fornecedor da última compra, com quantidade, preço e custo estimado; cada grupo vai como está para `POST /pedidos` |
| `POST /api/v1/pedidos` · `GET /api/v1/pedidos/{id}` | Faz o pedido (`fornecedor_id`, `feito_em`, `previsto_para`, `observacao` opcionais; `itens` com `insumo_id`, `quantidade` e `valor_unitario`) / um pedido. `422` para insumo repetido, data futura, previsão antes do pedido, fornecedor desativado ou inexistente |
| `PUT /api/v1/pedidos/{id}` | Altera o pedido aberto, antes de chegar qualquer coisa (senão `409`): os campos enviados e as linhas |
| `POST /api/v1/pedidos/{id}/cancelar` | O que falta chegar não vem mais; o que chegou fica. Recebido inteiro é `409` |
| `POST /api/v1/pedidos/{id}/receber` | A carga que chegou (`data`, padrão hoje; `itens` com `item_id`, `quantidade`, `validade` e `valor_unitario` opcionais): cada linha vira uma entrada com o fornecedor, o preço e quem conferiu; devolve o pedido (`parcial` ou `recebido`), as `movimentacoes` criadas e os `avisos` (carga a mais). Cancelado ou recebido é `409` |
| `POST /api/v1/importacoes` | Movimentações de uma planilha: `xlsx` (base64) ou `conteudo` (texto do CSV). Sem `confirmar`, só confere e resume, com o total de cada insumo; com erro, nada é gravado e a resposta lista os erros por linha |
| `GET /api/v1/importacoes/modelo.xlsx` | Planilha modelo formatada, com os insumos cadastrados para escolher da lista |
| `GET /api/v1/relatorio.xlsx` | Relatório do estoque em Excel, com as abas Pedidos (o que falta chegar) e Talhões. A aba Movimentações tem o formato da importação (com o talhão de cada aplicação e o fornecedor de cada compra): é também a cópia de segurança, e volta pela mesma tela |
| `POST /api/v1/analises` | Roda o motor sobre um insumo enviado no corpo (estoque, retiradas, lotes, período; `custo_medio`, `embalagem`, `pedido_minimo` e `a_caminho`, o que já foi pedido, opcionais) e devolve alertas, reposição e limitações. `422` para entrada inválida |
| `GET /api/v1/docs` | Swagger UI (desligado em `production`) |
| `GET /api/v1/openapi.json` | Schema OpenAPI (desligado em `production`) |

## 3. Frontend (`frontend/`)

| Caminho | Responsabilidade |
|---|---|
| `src/main.ts` | Instala Pinia e Router, importa o CSS |
| `src/router/` | Rotas. Páginas além do Painel entram por `import()` dinâmico. **O menu é derivado das rotas** (`meta.menu`): registrar uma tela é um lugar só |
| `src/layouts/` | `AppLayout`: menu lateral fixo no desktop, barra de baixo no celular e no tablet, resumo de status |
| `src/pages/` | Uma página por rota: Painel (alertas, reposição com lista de compras para o WhatsApp, limitações), Insumos (cadastro), página do insumo (`/insumos/:id`: resumo, gráfico, alertas, movimentações, remover), Movimentações (entradas e saídas), Importar dados (Excel ou CSV, com prévia), Sistema |
| `src/components/` | Reutilizáveis, sem chamada à API: `CabecalhoDePagina`, `CartaoDeAlerta`, `CoberturaDoEstoque` (quanto tempo cada insumo dura), `EstadoVazio`, `GraficoDeEstoque`, `IconeSvg`, `IndicadorDeStatus`, `LogoCampoCerto`, `NumeroRolante`, `SeloDeGravidade` |
| `src/stores/` | Pinia: estado compartilhado e as ações que chamam os serviços. `estoque` guarda insumos (com a análise) e movimentações, e recarrega tudo a cada alteração |
| `src/services/http.ts` | **Cliente HTTP único** (Axios). Normaliza erro em `ApiError` |
| `src/services/*.ts` | Uma função por endpoint |
| `src/types/` | Tipos TypeScript dos contratos da API |
| `src/styles/main.css` | Tailwind v4: tokens da marca e de movimento (`@theme`), componentes base (`.cartao`, `.botao-*`, `.campo`, `.esqueleto`) e as transições (ver "Design e movimento") |
| `public/modelo-movimentacoes.csv` | Modelo alternativo em CSV, servido como arquivo estático (com BOM, para o Excel abrir os acentos); o principal é o `.xlsx` gerado pela API |
| `tests/unit/` | Vitest + Vue Test Utils |

**Para o login** (a API já está pronta, seção 2, "Autenticação e papéis"), o site precisa: tela
de login (`POST /auth/entrar`, com `dispositivo` como "Navegador"), guardar o token (em
`sessionStorage` ou `localStorage`; nunca na URL) e mandá-lo em todo pedido pelo interceptador
do `services/http.ts` (`Authorization: Bearer <token>`); no `401`, apagar o token e voltar ao
login com a frase da API; no `403`, mostrar a frase sem deslogar; esconder dos funcionários
(`usuario.papel`) o que é do dono (cadastro, remover, importar, relatório, Usuários); tela de
Usuários para o dono e "Trocar senha" para todos; "Sair" chama `POST /auth/sair`. Mostrar
`lancado_por` nas movimentações.

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
  encolhendo um pouco.
- **Trabalho em andamento e resultado:** barra de "trabalhando" ao conferir a planilha, ícone
  que gira ao verificar o sistema, sinal de concluído que se desenha, esqueleto no lugar do
  conteúdo que está chegando.
- **O que não pode esperar:** só o ponto do selo "Urgente" pulsa (uma cópia dele cresce e
  some). Nada mais anima em loop.

### Celular

O produtor usa o CampoCerto no galpão, com o celular na mão, muitas vezes um Android de
entrada (360 px de largura). Abaixo de 1024 px:

- **Barra de baixo** no lugar do menu lateral: as cinco telas ao alcance do polegar, com o
  número de urgentes no Painel. O rótulo curto vem da rota (`meta.menu.curto`). Tocar de novo
  na aba da tela atual sobe para o topo; trocar de tela começa do topo, e o "voltar" do
  celular devolve a rolagem. Com o teclado aberto num campo de texto, a barra some para não
  cobrir o campo.
- **Listas no lugar de tabelas** (abaixo de 768 px): Insumos vira um cartão por insumo, com
  "Alterar" à mão; Movimentações vira um extrato agrupado por dia ("Hoje", "Ontem", dia da
  semana), com o dia preso no alto ao rolar.
- **Toque:** em tela de toque, botões com pelo menos 44 px de altura; campos com letra de
  16 px (abaixo disso o iPhone dá zoom); "Lançar" e "Enviar pelo WhatsApp" na largura toda.
  Ao lançar, a confirmação aparece ao lado do botão, e o Android vibra de leve.
- **Instalável** na tela inicial (`manifest.webmanifest`, ícones e metas da Apple): abre em
  tela cheia, como um app, respeitando entalhe e barra de gestos (`env(safe-area-inset-*)`).
  Sem modo offline: os dados vêm da API.

No desktop nada disso aparece: a partir de 1024 px a tela é a mesma de antes, pixel a pixel.

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

**Para lançar sem sinal** (a API já está pronta, seção 2, "Lançamento offline do app"), o app
precisa:

1. **Gerar um uuid v4 por lançamento**, na hora em que o produtor lança, e guardá-lo junto: é o
   mesmo uuid em todo reenvio. Nunca um uuid novo para reenviar.
2. **Guardar a fila no celular** (armazenamento que sobrevive a fechar o app) e mostrar o
   lançamento como "aguardando envio".
3. **Mandar a fila por `POST /movimentacoes/lote`**, em lotes de até 500, na ordem em que foram
   lançados; com sinal também, para ter um caminho só.
4. **Reenviar o mesmo lote até receber o resultado.** Sem resposta (timeout, sinal caiu, `5xx`),
   manda de novo: o que já entrou volta `ja_existia`. Só tira da fila o item que voltou com
   resultado.
5. **Opcional, o talhão:** a retirada para uso pode levar `talhao_id` (da lista de
   `GET /talhoes`, guardada no celular). Se o talhão foi removido no site antes do envio, o item
   volta `recusada` dizendo isso.
6. **Tratar cada resultado:** `gravada` e `ja_existia` saem da fila; `recusada` não vai mudar
   reenviando: sai da fila e aparece para o produtor com os `erros`, para corrigir e lançar de
   novo (com uuid novo, é outro lançamento). Os `avisos` também vão para a tela.

**Para o login**, o app precisa do mesmo que o site (seção 3), mais: guardar o token no
armazenamento seguro do celular (Keystore/Keychain, `flutter_secure_storage`), não em texto
puro; mandar `dispositivo` no login ("Celular do Zé"); a sessão vale 30 dias, então o login é
raro, mas o `401` pode chegar no **envio da fila**: aí a fila **fica** no celular (nada foi
gravado), o app pede o login e reenvia o mesmo lote com os mesmos uuids depois.

## 5. Infraestrutura

`compose.yaml` na raiz sobe `db` (PostgreSQL 18), `api` (imagem `backend/Dockerfile`, alvo `dev`,
com `--reload`) e `web` (Node 24 rodando o Vite). A API aplica `alembic upgrade head` ao subir
(`backend/docker/entrypoint.sh`); a espera pelo banco é o `healthcheck` do compose.

O Vite do container usa **polling** para perceber arquivos alterados (`VITE_POLLING` no
compose): no Docker Desktop do Windows, o código montado do host não gera eventos de arquivo
dentro do container, e sem isso o Vite serve a versão antiga até reiniciar.

Configuração por `.env` na raiz (modelo em `.env.example`). Variáveis obrigatórias sem default:
`ENVIRONMENT` e `DATABASE_URL` (montada pelo compose a partir de `POSTGRES_*`). `AUTENTICACAO`
tem padrão `false`, mas em `production` é obrigatória e tem de ser `true`. O primeiro dono se
cria com `make usuario-dono LOGIN=maria NOME="Dona Maria"`.

## 6. Herdado do ArkoHub × decidido diferente

O ArkoHub é um SaaS multi-tenant de ferramentas para escritórios (FastAPI + Vue 3/Vuetify +
PostgreSQL com RLS + MinIO + Redis + worker). O CampoCerto aproveita os **padrões**, não as
tecnologias que não se aplicam.

**Aproveitado**

- Monorepo `backend/` + `frontend/` com responsabilidades separadas; FastAPI como fonte da verdade
  do contrato.
- `Settings` com pydantic-settings, validado no boot, **`ENVIRONMENT` obrigatório e restrito** a
  valores conhecidos (fail-closed) e `/docs` desligado em produção. O mesmo critério vale para a
  autenticação: em produção, sem `AUTENTICACAO=true` a API não sobe.
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
| MinIO, Redis, worker, ClamAV, rate-limit por IP | Não entrou | Nenhum requisito do CampoCerto pede, por ora. Contra adivinhação de senha, há o bloqueio por usuário, no banco |
| Auth com sessão em Redis, papéis por tenant | Sessão no PostgreSQL (token opaco, SHA-256), dois papéis fixos | Sem Redis no stack; uma fazenda, dono e funcionário bastam |
| mypy strict, import-linter, dependency-cruiser, cobertura 90% | ruff + vue-tsc + eslint | Proporcional ao tamanho; os gates entram se as regras de camada começarem a ser violadas |

## 7. Próximas decisões (pendentes)

1. **Login nas telas.** A API já tem login com papéis (seção 2, "Autenticação e papéis"); o site
   e o app ainda não têm a tela de login nem mandam o token (seções 3 e 4), por isso a
   autenticação fica desligada no desenvolvimento. Enquanto isso, com ela desligada, qualquer um
   que alcance a tela lê e altera tudo (as portas da API e do banco ficam só em 127.0.0.1; a do
   front fica aberta na rede).
2. **Geração de tipos TS a partir do OpenAPI** (`openapi-typescript`) quando a API crescer. Com o
   app, os modelos em Dart entram na mesma conta.
3. **App nas lojas.** Ícone, assinatura do Android, conta de desenvolvedor da Apple e a API em
   `https://` em algum endereço público.
4. **Reais nas telas.** A API já devolve preço, custo médio, valor em estoque, embalagem, pedido
   mínimo e o `GET /resumo`; o site e o app ainda não têm campo para o preço ao lançar uma
   compra nem para a embalagem no cadastro, e não mostram o resumo. As justificativas, que as
   telas já exibem, trazem os valores.
5. **Talhões nas telas.** A API já tem o cadastro de talhões, a carência no insumo, a aplicação
   (`talhao_id` na retirada e no lote) e a leitura com carência e custo por hectare; o site e o
   app ainda não têm a tela de Talhões, o campo de carência no cadastro do insumo nem a escolha do
   talhão ao lançar uma retirada. Hoje, o talhão em carência aparece no relatório (aba Talhões) e
   no `/docs`.
6. **Compras nas telas.** A API já tem fornecedores, pedidos, a sugestão de pedido, o
   recebimento e o `em_pedido` de cada insumo (seção 2, "Fornecedores e pedidos de
   compra"); o site e o app ainda não têm a tela. O site precisa de: Fornecedores
   (cadastro, desativar, o preço pago por insumo); o campo fornecedor ao lançar uma compra;
   "Fazer pedido" a partir da sugestão (`GET /pedidos/sugestao`, confirmar e
   `POST /pedidos`, no lugar ou ao lado da lista do WhatsApp); a lista de pedidos com
   cancelar; mostrar `em_pedido` e `chegada_prevista` no insumo e `precos_por_fornecedor` na
   página dele. O app precisa, no mínimo, de "Receber pedido": a lista dos abertos e
   parciais, a quantidade que chegou por linha (com validade), e `POST
   /pedidos/{id}/receber` com os `avisos` na tela. O recebimento não está na fila offline:
   precisa de sinal (o servidor trava o pedido e confere o que já chegou). Enquanto isso, o
   relatório (aba Pedidos) e o `/docs` mostram tudo.

Decididas desde a versão anterior deste documento: a autenticação existe (dono e funcionário,
obrigatória em produção, seção 2); a importação de planilha existe (Excel e
CSV, seção 2); o ECharts entrou com o gráfico do insumo; o Pandas não entrou, porque nem o motor de
análise nem a importação precisaram; o `openpyxl` entrou para ler e gerar `.xlsx`.
