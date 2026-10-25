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
| `app/core/database.py` | Engine (com os tempos-limite), sessão, a dependência `get_db` e a conferência do papel com que a API conecta |
| `app/papel_da_aplicacao.py` | Comando que cria e acerta o papel da aplicação no PostgreSQL (roda no entrypoint, como o dono do banco) |
| `app/core/senha.py` | Hash Argon2id da senha (`argon2-cffi`), com o sal e os parâmetros gravados junto; confere também as senhas antigas em scrypt |
| `app/api/router.py` | Agrega as rotas da v1 (`/api/v1`), cada grupo com o seu nível de permissão |
| `app/api/permissoes.py` | As dependências de cada nível (sessão, funcionário, dono) e quem fez o pedido |
| `app/api/protecoes.py` | Os middlewares de todo pedido: cabeçalhos de segurança, `X-Request-ID` e log de acesso, o 500 com id, o limite de escritas por IP e o de 8 MB do corpo (ver "Blindagem da API") |
| `app/core/limite_de_taxa.py` | Contador de tentativas por janela de tempo (a interface e a versão em memória) |
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
| `app/domain/relatorio_por_periodo.py` | O relatório por período: os meses, semanas ou dias de um intervalo (cortados nas pontas, com teto de 400) e, em cada um, o consumo por insumo, o gasto, as perdas e os totais por categoria e por fornecedor | As mesmas: recebe os lançamentos e os insumos já lidos, devolve as somas |
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
| `app/models/estoque.py` | `categorias` (nome único), `insumos` (com `embalagem`, `pedido_minimo`, `carencia_dias` e `categoria_id` opcionais), `talhoes` (nome, `area_ha`, `cultura`) e `movimentacoes` (entrada ou saída, data, quantidade, validade, `motivo`: vazio, `descarte` ou `inventario`, `valor_unitario`, o preço da compra, `uuid`, o identificador gerado pelo app, `talhao_id`, onde a retirada foi aplicada, `usuario_id`, quem lançou, `fornecedor_id`, de quem foi a compra, e `item_do_pedido_id`, o pedido que a entrada recebeu). **O estoque atual não é coluna**: é a soma das movimentações, calculada na leitura. Uma fonte da verdade só. O custo médio também não: sai das compras |
| `app/services/estoque.py` | Casos de uso: cadastro, movimentações, a análise de cada insumo a partir do banco e o saldo dia a dia (histórico do gráfico). As rotas falam só com os serviços (este, `importacao`, `planilha_modelo` e `relatorio`) |
| `app/services/importacao.py` | Importação de movimentações por planilha (Excel ou CSV), ver abaixo |
| `app/services/planilha_modelo.py` | A planilha modelo da importação e os estilos das planilhas geradas (cores da marca, títulos, impressão) |
| `app/services/relatorio.py` | O relatório em Excel: resumo (com os totais em reais), alertas, reposição, situação de cada insumo, talhões (carência e custo) e todas as movimentações |
| `app/services/talhoes.py` | Cadastro de talhões e a leitura de cada um: carência e custo calculados das aplicações, com o custo médio pela mesma regra da tela do insumo |
| `app/services/sincronizacao.py` | A fila de lançamentos do app (`POST /movimentacoes/lote`): grava item a item, traduz os erros de validação em frases e calcula os avisos (ver abaixo) |
| `app/services/categorias.py` | Cadastro das categorias, com quantos insumos cada uma tem |
| `app/services/relatorio_por_periodo.py` | O relatório por período a partir do banco, em três consultas: as movimentações do período (com os filtros da lista), os insumos delas e as compras com preço, para o custo médio |
| `app/services/resumo.py` | A visão geral em reais (`GET /resumo`): soma o que `estoque.listar_insumos` já analisou, mais as perdas |
| `app/models/compras.py` | `fornecedores` (nome único, contato, telefone, cidade, observação, `ativo`), `pedidos` (fornecedor, `situacao`, `feito_em`, `previsto_para`, observação, quem fez) e `itens_do_pedido` (insumo, quantidade, preço combinado, `quantidade_recebida`) |
| `app/services/fornecedores.py` | Cadastro dos fornecedores e o detalhe com as compras recentes e o preço médio pago por insumo |
| `app/services/pedidos.py` | Pedidos de compra: fazer, alterar, cancelar e receber (a carga vira as entradas); a situação pelo que já chegou |
| `app/services/sugestao_de_pedido.py` | O pedido sugerido: as reposições do motor, agrupadas pelo fornecedor da última compra, com o preço dela |
| `app/models/usuario.py` | `usuarios` (login em minúsculas, hash da senha, papel, ativo, falhas seguidas e bloqueio) e `sessoes` (o SHA-256 do token, validade, encerramento, aparelho) |
| `app/services/autenticacao.py` | Login, a sessão conferida a cada pedido, sair, trocar a senha e o bloqueio por senhas erradas |
| `app/services/usuarios.py` | Gestão pelo dono: cadastrar, alterar, desativar, redefinir a senha; o último dono ativo |
| `app/usuarios.py` | O comando que cria o primeiro dono no servidor (`make usuario-dono`) |
| `app/models/auditoria.py` | `eventos_de_auditoria`: quem, quando, a ação, sobre o quê, o conteúdo em JSONB e de onde; somente acrescentar |
| `app/services/auditoria.py` | Grava o evento na transação da ação (sem commit, sem segredo) e o consulta (`GET /auditoria`) |
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

### Categorias, filtros e relatório por período

Com dezenas de insumos e anos de movimentações, a lista inteira deixa de servir: o produtor quer
"os defensivos", "o que a revenda X vendeu em março", "quanto gastei por mês". Decisões:

- **Categoria** (`categorias`, nome único): a migration 0011 já cria as de partida de uma
  propriedade de Rondônia, com lavoura (soja, milho, café) e gado: Fertilizante, **Corretivo de
  solo** (à parte: o calcário é a maior compra de quem abre área em solo ácido, e somado ao adubo
  esconderia os dois), Defensivo agrícola, Semente e muda (o café conilon se planta por muda),
  Medicamento veterinário, Nutrição animal, Combustível e lubrificante (o diesel do trator) e
  Outros. O dono cadastra, renomeia e remove outras (`/categorias`); a resposta diz quantos
  insumos cada uma tem.
- **No insumo**, `categoria_id` é opcional (FK `RESTRICT`), e a resposta traz também o nome
  (`categoria`). Como a embalagem, o `PUT` sem o campo mantém o gravado; `null` de propósito tira.
  Categoria inexistente é `422`. **Remover a categoria com insumo é `409`**: os insumos ficariam
  sem categoria calados, e os totais por categoria mudariam sem ninguém pedir.
- **Filtros de `GET /insumos`** (opcionais, somados): `categoria_id`, `busca`, `gravidade` (quem
  tem algum alerta dela) e `com_alerta`. Os de alerta filtram a lista já analisada: o alerta não
  é coluna, e a análise de cada insumo lê as movimentações dele de qualquer jeito.
- **Busca sem diferenciar maiúsculas nem acentos** ("ureia" acha "Uréia"), feita em Python
  (decompõe com NFKD, tira os acentos, `casefold`) sobre id e nome dos insumos, e não no banco. O
  PostgreSQL só ignora acento com a extensão `unaccent` (que precisaria ser instalada e não existe
  no SQLite dos testes), e o `lower()` do SQLite não conhece letra acentuada: no banco, os dois
  dariam resultados diferentes. Os insumos de uma fazenda são centenas, e ler id e nome é barato.
  Nas movimentações, a busca é no nome do insumo e vira `insumo_id IN (...)`.
- **Filtros de `GET /movimentacoes`** (opcionais, somados, além de `insumo_id`): `tipo`, `motivo`
  (`descarte`, `inventario` ou `nenhum`, a movimentação sem motivo: a retirada para uso, na saída,
  e a compra, na entrada), `categoria_id`, `talhao_id`, `fornecedor_id`, `usuario_id`, `desde` e
  `ate` (inclusive; invertido é `422`) e `busca`.
- **Paginação** com `deslocamento`, junto do `limite` de sempre. O total com os mesmos filtros vai
  no cabeçalho **`X-Total-Count`**: o corpo continua a lista de antes, e o site e o app não
  quebram (mesma origem, sem CORS para expor o cabeçalho). Ordem estável: data desc e **id desc**
  desempatando o mesmo dia; sem o id, duas do mesmo dia podiam trocar de lugar entre um pedido e
  outro, e uma linha apareceria em duas páginas e outra em nenhuma. Paginação por deslocamento, e
  não por cursor: o volume de uma fazenda (dezenas de milhares) não pede mais, e a tela pode pular
  para a página N.
- **Índices** (migration 0011), conferidos com `EXPLAIN` no PostgreSQL com 50 mil movimentações
  (`tests/integracao/test_fluxo_categorias_e_relatorios.py`):
  - `ix_movimentacoes_data_id` `(data, id)`: a lista sem filtro sai por `Index Scan Backward`
    lendo só as 200 linhas da página, sem ordenar a tabela; o período do relatório (30 dias de
    quase três anos) sai por `Bitmap Index Scan` nele, sem ler a tabela inteira.
  - `ix_movimentacoes_insumo_id_data_id` `(insumo_id, data, id)`: as movimentações de um insumo e
    o total delas (`Bitmap Index Scan`); com mil linhas do insumo espalhadas pela tabela, o
    PostgreSQL prefere buscá-las pelo índice e ordenar as mil na memória, escolha dele pelo custo.
    Começa por `insumo_id`, então **substitui** o índice simples dela (um índice a menos a gravar a
    cada lançamento) e continua servindo à FK (o `CASCADE` ao remover o insumo).
  - As outras FKs de `movimentacoes` (talhão, usuário, fornecedor, pedido) já tinham índice, e
    `insumos.categoria_id` ganhou o seu (o filtro e a trava do `RESTRICT`).
  - O total sem filtro (`count(*)` da tabela inteira) é uma leitura sequencial: com 50 mil linhas,
    a lista com o total respondeu em 0,07 s pela API.
- **Relatório por período** (`GET /relatorios/periodo`): por `mes`, `semana` (segunda a domingo)
  ou `dia`, de `desde` a `ate` (inclusive; sem eles, os últimos 12 meses até hoje), com filtros
  opcionais de categoria, insumo, talhão e fornecedor. Cada período, cortado nas pontas e **zerado
  quando não houve movimento** (o gráfico não tem buraco), traz:
  - **consumo** por insumo: só a retirada para uso (descarte e falta da contagem são perda; a
    sobra não é compra nem consumo). **Quantidade só se soma dentro do mesmo insumo**, na unidade
    dele: 150 kg de ureia e 4 L de glifosato não dão "154" de nada. Em reais (quantidade × custo
    médio), sim, e é assim que entra nos totais por categoria;
  - **gasto**: o que se pagou nas compras com preço; as sem preço ficam fora, e o relatório diz
    quantas (`compras_sem_preco` e uma limitação);
  - **perdas**: descarte e falta da contagem pelo custo médio, a mesma conta do `GET /resumo` (o
    teste confere que os dois batem);
  - **totais por categoria** (gasto, consumo e perdas em R$; sem categoria por último) e **por
    fornecedor** (gasto, compras, quantas sem preço; a compra sem fornecedor por último).

  O `total` do intervalo inteiro tem a mesma forma, e as `limitacoes` dizem o que as somas não
  sabem: compras e perdas sem preço, consumo sem valor, o custo médio de hoje (e não o da época),
  e o que os filtros de talhão e de fornecedor deixam de fora (compra e perda não são de talhão;
  consumo e perda não são de fornecedor).
- **Puro e sem N+1.** As somas moram no domínio (`app/domain/relatorio_por_periodo.py`), testadas
  com listas. O serviço faz três consultas qualquer que seja o período ou o número de insumos (as
  movimentações do período, com o fornecedor junto; os insumos com a categoria; as compras com
  preço desses insumos, para o custo médio), e o teste conta as consultas.
- **Teto de 400 períodos** (por dia, uns 13 meses; por semana, quase 8 anos): acima, `422` com a
  frase. É contado antes de montar os períodos e antes de consultar o banco.
- **Aba Por mês** no `relatorio.xlsx`: os últimos 12 meses (gasto, compras sem preço, consumo e
  perdas em R$), os mesmos números da rota. Fica antes da aba Movimentações e com outro nome: a
  importação lê só aquela, e a cópia de segurança volta igual.
- **Planilha:** coluna opcional `categoria`, usada **só ao cadastrar um insumo novo** (o já
  cadastrado fica com a da tela de Insumos: a planilha é de movimentações, e mudar o cadastro por
  ela seria uma segunda tela de cadastro, escondida). A que não existe é **cadastrada pelo nome**,
  como o fornecedor, e não recusada como o talhão: só precisa do nome, e a cópia de segurança
  restaurada num sistema vazio devolve cada insumo à sua categoria. A prévia lista
  `categorias_novas`; o mesmo insumo novo em duas categorias é erro na linha. O modelo traz a
  coluna, a lista (que só sugere) e a aba Categorias cadastradas; o relatório escreve a categoria
  de cada insumo na aba Movimentações.
- **Permissões:** ler categorias e o relatório por período é do **funcionário**, como o
  `/resumo`: ele já lê o custo médio, o preço de cada compra e o preço pago a cada revenda, e o
  relatório são as mesmas contas somadas; escondê-lo pediria um schema por papel sem proteger nada
  que ele já não veja. Cadastrar, alterar e remover categoria é do dono. O `relatorio.xlsx`, com a
  cópia de segurança, continua só do dono.
- **Demonstração:** cada insumo fictício vai para a sua categoria de partida, reaproveitada pelo
  nome (num banco migrado, nenhuma é criada); o `limpar` não as apaga, e os alertas do roteiro não
  mudam.
- **Migration 0011.** O downgrade apagaria as categorias cadastradas pelo dono e a categoria de
  cada insumo: ele se recusa enquanto houver alguma categoria além das de partida ou algum insumo
  com categoria, e só segue com `alembic -x descartar_categorias=sim downgrade 0010`. Ele devolve
  o índice simples de `insumo_id`.

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
  importação. O que é removido, alterado e as tentativas de login vão para a trilha de
  auditoria (abaixo).
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
| Funcionário | funcionário e dono | `GET /insumos`, `GET /insumos/{id}`, `GET /movimentacoes`, `GET /talhoes`, `GET /talhoes/{id}`, `GET /resumo`, `GET /categorias`, `GET /relatorios/periodo`, `GET /fornecedores`, `GET /fornecedores/{id}`, `GET /pedidos`, `GET /pedidos/{id}`, `GET /pedidos/sugestao`; `POST /movimentacoes`, `POST /movimentacoes/lote`, `POST /insumos/{id}/inventario`, `POST /pedidos/{id}/receber` |
| Dono | só o dono | `POST`/`PUT`/`DELETE /insumos`, `DELETE /movimentacoes/{id}`, `POST`/`PUT`/`DELETE /talhoes`, `POST`/`PUT`/`DELETE /categorias`, `POST`/`PUT`/`DELETE /fornecedores`, `POST /pedidos`, `PUT /pedidos/{id}`, `POST /pedidos/{id}/cancelar`, `POST /importacoes`, `GET /importacoes/modelo.xlsx`, `GET /relatorio.xlsx`, `POST /analises` |
| Gestão | só o dono, sempre com login | `GET /usuarios`, `POST /usuarios`, `PUT /usuarios/{id}`, `PUT /usuarios/{id}/senha`, `GET /auditoria` |

O funcionário lê os insumos com o custo médio e o valor em estoque (as telas que ele usa são as
mesmas), e o preço pago a cada fornecedor; o relatório, com todos os preços e a cópia de
segurança, é só do dono. O funcionário recebe a carga de um pedido, mas não faz, altera nem
cancela pedido.

### Trilha de auditoria

Apagar uma movimentação, um insumo ou um usuário não deixava rastro: ninguém sabia quem apagou
os 200 kg de ureia lançados ontem, nem quem deu a si mesmo o papel de dono. Agora o que é
sensível ou destrutivo grava um evento em `eventos_de_auditoria` (`app/models/auditoria.py`,
`app/services/auditoria.py`), que o dono lê em `GET /auditoria`. Decisões:

- **O que entra.** O que apaga, o que muda um cadastro de que outros dependem, o que mexe em
  quem entra no sistema e as tentativas de entrar à força. Cada ação tem um código estável (a
  tela e os filtros dependem dele; um código novo entra em `ACOES`, e um desconhecido é
  recusado):

  | Ação | `dados` |
  |---|---|
  | `movimentacao.removida` | O conteúdo inteiro, o bastante para relançá-la à mão: insumo, tipo, data, quantidade, validade, motivo, preço, talhão, fornecedor, uuid, quem lançou e a linha de pedido, com os nomes ao lado dos ids (podem não existir mais quando alguém ler) |
  | `insumo.removido` | O cadastro, cada movimentação que saiu junto (no mesmo formato), as linhas de pedido e os pedidos que ficaram vazios |
  | `talhao.removido` · `categoria.removida` · `fornecedor.removido` | O cadastro inteiro |
  | `insumo.alterado` · `talhao.alterado` · `categoria.alterada` · `fornecedor.alterado` · `pedido.alterado` | O antes e o depois **só do que mudou**; nada mudou, nada é gravado |
  | `pedido.cancelado` | A situação de antes, a revenda e o que faltava chegar de cada linha |
  | `importacao.confirmada` | O resumo (formato, linhas, entradas e saídas, período, total por insumo, insumos, fornecedores e categorias novos, quantas já estavam lançadas), e não cada linha: são milhares, a planilha é a cópia delas e cada movimentação já diz quem a lançou |
  | `usuario.criado` · `usuario.alterado` | Login, nome e papel; na alteração, o antes e o depois (virar dono, ser desativado) |
  | `usuario.senha_redefinida` · `usuario.senha_trocada` | O login (e, na redefinida, se desfez um bloqueio). Quem redefine a senha de alguém pode entrar como ele; a sessão roubada que troca a senha tranca o dono fora |
  | `login.recusado` · `login.bloqueado` | O login e o motivo (`senha_incorreta`, `bloqueado`, `usuario_desativado`, `senha_atual_incorreta`), que a resposta não conta a quem tentou; no bloqueio, até quando |
  | `login.limitado` | Um IP passou do limite de tentativas de login (ver "Blindagem da API"): o `limite`, a janela (`janela_segundos`, 60 ou 3600) e `liberado_em`. Um evento por rodada, na primeira recusa, e não um por tentativa: quem insiste não enche a trilha. Sem usuário nem login (o IP vai na coluna `ip`) |
  | `demo.carregada` · `demo.limpa` | Quanto saiu e quanto entrou (a demonstração apaga e cria em massa) |

- **O que não entra, de propósito.** A leitura (o relatório inclusive). O lançamento comum
  (`POST /movimentacoes`, a fila do app, a contagem do galpão, o recebimento do pedido): a
  movimentação já guarda quem a lançou (`usuario_id`), e um evento por lançamento só repetiria
  isso. A carga **a mais** no recebimento também não: a entrada fica, com quem conferiu e a
  linha do pedido, e o excesso se vê comparando `quantidade_recebida` com `quantidade`; se
  alguém a remover depois, aí sim há evento. O cadastro novo (insumo, talhão, pedido...): ele
  mesmo é o registro, e nada se perde. O login aceito e o sair: a sessão (`sessoes`) já guarda
  quem, quando, o aparelho e quando foi encerrada. O login que **não existe**: não há a quem
  atribuir, e o que se digitou no campo do login pode ser a senha. A prévia da importação e a
  planilha com erro: nada é gravado. Não há rota que apague pedido (ele se cancela, e o
  cancelamento entra).
- **Quem e de onde.** `usuario_id` de quem está logado (vazio com a autenticação desligada, num
  comando no servidor e no login recusado, em que quem tentou não é conhecido: o alvo vai em
  `entidade_id`). `origem`: `api` ou `terminal` (a demonstração e o `criar-dono`). `ip`: o que
  o uvicorn viu (`request.client.host`). O `X-Forwarded-For` **não** é lido: qualquer um o
  escreve, e um IP forjado na trilha é pior que nenhum. Atrás de um proxy, o IP é o do proxy,
  a não ser que o uvicorn confie nele (`--forwarded-allow-ips`) e troque pelo do cliente.
  `dispositivo`: o que o aparelho disse ser no login ("Celular do Zé"), declarado, não prova.
  `ocorrido_em`: o relógio do servidor, nunca o do pedido.
- **Atômico.** `registrar` põe o evento na sessão do serviço e **não faz commit**: ele vai junto
  com a ação. Falhou a ação (o `409` do talhão com aplicação, o nome repetido), não há evento;
  falhou o evento (um segredo nos dados, o banco recusando o `INSERT`), a ação não acontece. O
  login recusado e o bloqueio entram na mesma transação da contagem de falhas. A remoção trava
  a linha (`FOR UPDATE`): duas remoções ao mesmo tempo não deixam dois eventos, e o lançamento
  feito no meio não some no `CASCADE` sem estar no evento.
- **Nunca segredo.** `registrar` recusa (`ValueError`, e a ação não acontece) `senha`,
  `senha_hash`, `senha_atual`, `senha_nova`, `token` e `token_hash` em qualquer nível dos
  dados, e os serviços montam os dados à mão, campo a campo, sem o modelo inteiro. Quem lê a
  auditoria não pode sair com uma senha nem com um login aberto.
- **Somente acrescentar, em três camadas.** Um rastro que quem apagou pode apagar não prova
  nada:
  1. o papel da aplicação só tem `INSERT` e `SELECT` na tabela. A migration 0012 tira o
     `UPDATE`, `DELETE` e `TRUNCATE` que o `ALTER DEFAULT PRIVILEGES` lhe daria ao nascer;
  2. `python -m app.papel_da_aplicacao`, a cada subida, refaz o `GRANT` em todas as tabelas e
     logo depois os tira de novo desta (`SOMENTE_ACRESCENTAR`);
  3. um gatilho (`somente_acrescentar`) recusa `UPDATE` e `DELETE` de **qualquer um**, o dono
     inclusive. Escolhido porque o dono é quem roda migration e abre o `psql`: o `DELETE` à mão
     por engano, ou a migration futura que "limpa" dados, não apagam o rastro. O dono ainda
     pode derrubar o gatilho (é dono), mas não sem querer. O `TRUNCATE` (que não dispara
     gatilho de linha) fica só com o dono: é como os testes esvaziam o banco descartável.

  Provado no PostgreSQL real (`tests/integracao/test_fluxo_auditoria.py`): conectado como o
  papel da aplicação, `UPDATE`, `DELETE` e `TRUNCATE` dão `42501`; o dono leva a recusa do
  gatilho.
- **`GET /auditoria`, só do dono e sempre com login** (como a gestão de usuários: a trilha diz
  quem tentou entrar e de onde). Os mais recentes primeiro (`ocorrido_em`, desempate pelo id),
  com `feito_por` (o nome) ao lado do `usuario_id`. Filtros que se somam: `acao` (o código, ou
  o grupo, como `usuario` ou `login`; o grupo vira a lista dos códigos dele, e não um `LIKE`, e
  o que não existe é `422` com os grupos, e não uma lista vazia que parece "nada aconteceu"),
  `usuario_id`, `entidade` e `entidade_id`, `desde` e `ate` (dias de Rondônia, inclusive).
  Página: `limite` (padrão 200, até 1000) e `deslocamento`, com o total em `X-Total-Count`.
- **Índices** na ordem da consulta: `(ocorrido_em, id)`, `(acao, ocorrido_em, id)`,
  `(usuario_id, ocorrido_em, id)` (serve também à FK) e `(entidade, entidade_id, ocorrido_em,
  id)`. São poucas gravações (ações raras), e quatro índices custam pouco.
- **`usuario_id` com FK `RESTRICT`**: usuário não se apaga, desativa; e um `SET NULL` seria um
  `UPDATE`, que o gatilho recusa.
- **Migration 0012.** O downgrade apagaria a trilha inteira: ele se recusa enquanto houver
  evento, e só segue com `alembic -x descartar_auditoria=sim downgrade 0011`.
- **Sem retenção, por ora.** A tabela só cresce, devagar, porque as ações são raras; o que pode
  crescer rápido é `login.recusado` de um ataque a um login que existe (cada tentativa
  durante o bloqueio também grava, para o dono ver que continuam). Cada tentativa gasta o hash
  lento da senha, e o limite por IP (ver "Blindagem da API") segura o ritmo: no máximo 20
  tentativas por hora de cada IP chegam a ser conferidas e gravadas.

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
  aberto. Por isso, em camadas: pedido acima de 8 MB recusado com `413` sem ler o resto do
  corpo, contando os bytes que chegam, e não só o `Content-Length` (`app/api/protecoes.py`,
  ver "Blindagem da API"; pelo proxy do Vite essa recusa antecipada chega como `502`, porque o proxy
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

### Banco: papéis e tempos-limite

O `POSTGRES_USER` do container oficial é **superusuário** e dono de tudo. Com a API conectada
com ele, uma falha nela daria o cluster inteiro: `DROP`, ler os outros bancos, `COPY ...
PROGRAM` rodando comando no servidor. E sem tempo-limite, uma consulta presa, um `FOR UPDATE`
esperando trava (login, recebimento de pedido) ou uma transação esquecida aberta seguravam a
conexão e as travas para sempre, e a API ficava pendurada. Decisões:

- **Dois papéis.** O **dono do banco** (`POSTGRES_USER`, na `MIGRATIONS_DATABASE_URL`) roda só
  o Alembic (DDL) e o comando que garante o outro papel. O **papel da aplicação**
  (`APP_DB_USER`, padrão `campocerto_app`, na `DATABASE_URL`) é o da API: não é superusuário,
  não cria papel nem banco, não é dono de nada, não tem `CREATE` no schema nem no banco; só
  `SELECT, INSERT, UPDATE, DELETE` nas tabelas e `USAGE, SELECT` nas sequências de `public`.
  Sem `TRUNCATE`, `REFERENCES`, `TRIGGER`, `ALTER`, `DROP`. Da `alembic_version`, só lê (para
  conferir um dia se o banco está em dia; quem a grava é o Alembic). Na trilha de auditoria
  (`eventos_de_auditoria`), só acrescenta e lê: `INSERT` e `SELECT`, sem `UPDATE` nem `DELETE`
  (ver Trilha de auditoria). `NOINHERIT`: posto dentro
  de outro papel por engano, não herda os poderes de lá.
- **A demonstração e o `criar-dono` usam o papel da aplicação.** Só fazem `INSERT` e `DELETE`,
  como a API: não há motivo para darem a um script os poderes que a API não tem.
- **Quem cria o papel: o entrypoint, a cada subida, depois das migrations**
  (`python -m app.papel_da_aplicacao`, como o dono). Cria o papel se não existe, acerta a senha
  e os atributos e refaz as permissões do zero (o que uma versão anterior tenha dado a mais
  sai), numa transação, com trava consultiva (duas réplicas subindo juntas não brigam).
  Idempotente. Escolhido no lugar de um script de `docker-entrypoint-initdb.d` porque esse só
  roda no volume **novo**: o banco que cada dev já tem, com dados, ficaria sem o papel. Nem
  numa migration, porque a senha é do ambiente, não do schema, e muda sem nova revisão. Depois
  das migrations, e não antes: no banco novo, as tabelas já existem quando as permissões são
  dadas.
- **Permissões que nascem com a tabela.** `ALTER DEFAULT PRIVILEGES FOR ROLE <dono> IN SCHEMA
  public`: a tabela (e a sequência) que uma migration futura criar já vem com o DML para o papel
  da aplicação, mesmo que rode sem o comando depois (`make migrate` com a API no ar). Vale para
  o que **esse** dono criar: migrations rodadas por outro papel precisam do comando de novo.
- **Senha:** de `APP_DB_PASSWORD`, só letras e números (vai numa URL), 12 ou mais; nunca em
  arquivo versionado. O nome e a senha saem da própria `DATABASE_URL`, uma fonte só. Vai ao
  servidor já cifrada em SCRAM (calculada pela libpq): nem um `log_statement` ligado no
  PostgreSQL a veria em claro, e as mensagens de erro do comando nunca a levam.
- **A API não carrega a senha do dono:** o entrypoint tira a `MIGRATIONS_DATABASE_URL` do
  ambiente antes do `uvicorn`. Os outros comandos do container (alembic, demonstração) seguem
  com ela. Em produção, o melhor é ir além: migrations num job à parte, e o container da API
  só com a `DATABASE_URL`.
- **Desenvolvimento simples.** Sem `MIGRATIONS_DATABASE_URL`, as migrations usam a
  `DATABASE_URL` (quem roda tudo no host com um papel só não configura nada a mais), e o
  comando não tem papel a garantir. A API sobe assim, avisando no log que está com poderes de
  dono.
- **Produção, fail-closed.** Ao subir em `production`, a API confere o papel com que conecta:
  superusuário, `CREATEROLE`, `CREATEDB`, dono (ou membro do dono) de tabela de `public`,
  `CREATE` no schema ou no banco, ou membro dos papéis que rodam comando e leem arquivo do
  servidor. Qualquer um deles, ou o banco inacessível para conferir, e ela **não sobe**,
  dizendo o que pôr em cada URL.
- **Tempos-limite na conexão da API** (opções `-c` da libpq, configuráveis no `config.py`, só
  valores positivos: zero no PostgreSQL é "sem limite"):

  | Limite | Padrão | Por quê |
  |---|---|---|
  | `statement_timeout` | 30 s | O maior comando medido com 50 mil movimentações (o máximo de uma planilha), na importação e no relatório: menos de 1 s. Folga para o banco crescer anos |
  | `lock_timeout` | 5 s | Nenhuma trava legítima dura mais que uma requisição curta; depois disso, "tente de novo" é melhor que fila |
  | `idle_in_transaction_session_timeout` | 60 s | A maior pausa medida dentro de transação: uns 7 s (a importação lendo 50 mil linhas). O relatório monta o Excel **depois** de terminar a leitura (eram 11 s com ela aberta) |
  | `pool_timeout` | 10 s | Espera por conexão livre no pool |
  | `pool_recycle` | 30 min | Firewall e proxy derrubam conexão parada sem avisar |

  Ficam na conexão, e não no papel (`ALTER ROLE ... SET`): validados no boot com o resto da
  configuração, e iguais para tudo que usa o engine da API. O Alembic tem engine próprio e **não
  os herda**: migration pode demorar e esperar trava.
- **Estourou, `503` com `Retry-After: 5`.** `statement_timeout` (57014), `lock_timeout` (55P03)
  e o pool sem conexão livre não são defeito do servidor nem do pedido: é espera que passa. A
  resposta é `503` com a frase para a tela ("O banco demorou demais...", "Outro pedido está
  mexendo nos mesmos dados agora...", sempre com "Tente de novo em alguns segundos"), e não
  `500` com traceback. Nem `409` (não há o que o produtor corrigir) nem `504` (a API não é um
  proxy). O log leva só o código, sem a consulta e os valores. Outro erro do banco (fora do ar,
  senha errada) e a transação derrubada por ficar parada um minuto seguem como erro do servidor:
  não passam sozinhos, e o segundo é defeito.
- **No lote do app, o item que estoura não vira `recusada`.** `recusada` pede ao produtor que
  confira e lance de novo, e o dado está certo: só esperou. O lote inteiro responde `503`; o que
  já foi gravado fica (um item, uma transação), e o reenvio, que o app faz sozinho, devolve-o
  como `ja_existia`.

### Blindagem da API

O que vale para **todo pedido**, antes de qualquer rota: middlewares ASGI puros em
`app/api/protecoes.py` (e não o `@app.middleware("http")` do Starlette, que não deixa embrulhar o
`receive`), mais o limite do login na própria rota. De fora para dentro: cabeçalhos de
segurança, registro do pedido, limite de escritas por IP, limite do corpo. Decisões:

- **Limite de tentativas de login por IP** (`POST /auth/entrar`): **10 por minuto e 20 por
  hora**. O bloqueio por usuário (5 erros, 15 minutos) protege cada login; este protege a
  fazenda de quem testa senhas em muitos logins, ou tranca todos de propósito, e enche a
  trilha. Os números: a fazenda inteira costuma sair pelo mesmo IP, e quem erra a senha 3
  vezes, ou dois funcionários entrando juntos, cabem com folga no minuto; a sessão dura 30
  dias, ninguém entra 20 vezes numa hora, e quem testa senhas fica em 480 por dia, e não 14
  mil. O `429` vem **antes** de conferir a senha: não gasta o hash lento, **não conta como erro
  do usuário** (senão quem passa do limite ainda bloquearia o login de alguém com tentativas
  que nem foram conferidas) e não grava `login.recusado`. Só a primeira recusa de cada rodada
  vira o evento `login.limitado`. As sessões já abertas não sentem nada: o limite é de quem
  tenta entrar.
- **Limite de escritas por IP:** **120 por minuto** nos `POST`, `PUT`, `PATCH` e `DELETE` (fora
  o login, que tem o dele e não gasta este), num middleware, antes de ler o corpo. A leitura
  não tem limite: o Painel recarrega tudo a cada alteração. 120 por minuto (2 por segundo, sem
  parar) é mais do que um escritório lança à mão; a fila do app vai num pedido só
  (`/movimentacoes/lote`, até 500 itens) e a planilha também. Segura o script que grava sem
  parar, sem atrapalhar ninguém. Sem evento de auditoria: não é tentativa de entrar à força.
- **Estourou, `429`** com `Retry-After` (os segundos exatos até caber de novo) e a frase com os
  minutos para cima: "Muitas tentativas de entrar a partir desta rede. Espere 1 minuto e tente
  de novo." / "Muitos pedidos seguidos a partir desta rede. ...". Quem insiste durante a recusa
  não conta nem empurra o fim dela. Janela deslizante exata (o instante de cada tentativa).
- **Qual IP:** o do `request.client.host`, o mesmo da auditoria. O `X-Forwarded-For` **não** é
  lido: qualquer um o escreve, e trocá-lo a cada tentativa zeraria a conta. Consequência: atrás
  de um proxy, conta o IP do proxy, e todos que passam por ele dividem a mesma cota. No
  desenvolvimento, o site passa pelo proxy do Vite (e as chamadas do host, pelo gateway do
  Docker): todos os usuários do site somam juntos, o que nos números acima ainda sobra para uma
  fazenda. Em produção atrás de um proxy reverso, o uvicorn tem de confiar nele
  (`--forwarded-allow-ips` com o IP do proxy) para ver o do cliente, ou o proxy limita por si.
- **Em memória do processo** (`LimiteEmMemoria`, em `app/core/limite_de_taxa.py`): basta com o
  uvicorn de um processo do compose. Com vários processos ou réplicas, cada um contaria à parte
  (o limite real seria o número deles vezes o configurado); reiniciar a API zera a conta. A
  interface (`LimiteDeTaxa.tentar(chave)`) é pequena para trocar por uma no PostgreSQL (uma
  tabela de tentativas e um `DELETE` das velhas) ou num Redis, sem mexer no resto. A memória tem
  teto (50 mil IPs; o que ficou mais tempo sem pedir sai primeiro), contra um ataque de muitos
  IPs; esquecer um IP só lhe devolve a cota, e o bloqueio por usuário no banco continua.
- **Configurável** em `config.py`: `LIMITE_POR_IP` (ligado por padrão; desligar é decisão
  explícita), `LIMITE_LOGIN_POR_MINUTO`, `LIMITE_LOGIN_POR_HORA` (não menor que o do minuto) e
  `LIMITE_ESCRITAS_POR_MINUTO`, todos maiores que zero. A suíte de testes o desliga, como faz
  com a autenticação (todo pedido do `TestClient` vem do mesmo "IP", e os cenários montados pela
  API gravam 120 movimentações num segundo); os testes do limite o ligam.
- **Limite real de 8 MB do corpo.** O de antes confiava no `Content-Length`: um pedido
  `Transfer-Encoding: chunked` não o traz e ia inteiro para a memória (o FastAPI lê o corpo
  todo antes de validar). Agora o `receive` é embrulhado e soma os bytes que chegam; ao passar
  de 8 MB, responde `413` ("Arquivo grande demais: o máximo é 5 MB.") e diz à API que o cliente
  se foi: ela para de ler, e o uvicorn fecha a conexão sem ler o resto. O `Content-Length`
  acima do limite continua recusado antes de ler um byte. A planilha de 5 MB (uns 6,7 MB em
  base64) continua cabendo.
- **Cabeçalhos de segurança em toda resposta** (inclusive erros, `413`, `429`, `500` e o
  Excel): `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy:
  no-referrer`, `Cross-Origin-Resource-Policy: same-origin` (o site é a mesma origem e o app não
  é navegador: nenhum dos dois sente) e `Cache-Control: no-store`. O `no-store` vai em **toda**
  resposta, e não só em `/auth`, `/usuarios` e `/auditoria`: quase tudo aqui é dado da fazenda
  (preços, estoque), nada é estático, e uma regra só não deixa rota nova escapar.
- **CSP:** nas respostas da API, a mais fechada (`default-src 'none'; frame-ancestors 'none';
  base-uri 'none'; form-action 'none'`): JSON e Excel não carregam nada, e se um dia uma
  resposta for aberta como página, nada roda dali. Não atinge o site, cuja página vem do Vite.
  O **Swagger** (`/api/v1/docs`, fora de produção) é página e tem a sua: o JS e o CSS do CDN
  que o FastAPI usa (`cdn.jsdelivr.net`), o ícone, `connect-src 'self'` para o "Try it out", e
  o script de dentro da página liberado **pelo hash**, calculado da página que sai (muda com a
  URL do schema e com a versão do FastAPI), e não por `'unsafe-inline'`, que deixaria rodar
  qualquer script injetado. O estilo em linha fica liberado (o Swagger escreve atributos
  `style`; estilo não roda código). Conferido no Edge headless: as operações aparecem, sem
  violação de CSP no console.
- **HSTS desligado no desenvolvimento** (`HSTS_SEGUNDOS=0`, o padrão): em `http://localhost`,
  ligado, o navegador recusaria o http de todos os projetos até o prazo vencer. Com HTTPS na
  frente, `HSTS_SEGUNDOS=31536000` (um ano) liga o `Strict-Transport-Security`.
- **`X-Request-ID` em toda resposta.** O do cliente (o app pode mandar o seu) é aceito só se
  tiver formato seguro: letras sem acento, números, hífen e sublinhado, até 64. Qualquer outra
  coisa (espaço, quebra de linha, acento) poderia forjar linhas no log ou cabeçalhos; vira um
  UUID novo.
- **Log de acesso estruturado:** uma linha JSON por pedido (logger `app.acesso`, nível INFO):
  `id`, `metodo`, `caminho` **sem a query string** (pode levar o que se buscou), `status`,
  `duracao_ms`, `usuario_id` (quando há login) e `ip`. Nunca corpo, cabeçalhos, token nem senha.
  O log de acesso do próprio uvicorn fica desligado na imagem (`--no-access-log` no
  `Dockerfile`): ele leva a query string, não tem o id nem o usuário, e cada pedido sairia em
  duas linhas.
- **Erro inesperado: `500` com frase e id.** O traceback vai para o log (logger `app.erro`, com
  o id, o método e o caminho); a resposta leva só "Algo deu errado no servidor. Tente de novo;
  se continuar, informe ao suporte o código do pedido." e `id_da_requisicao`, nunca o traceback.
  Pego no middleware do registro, e não num `exception_handler(Exception)`: o do Starlette roda
  por fora de todos os middlewares, e o `500` sairia sem o id e sem os cabeçalhos. O `503` dos
  tempos-limite do banco e o `422` do `DataError` também levam `id_da_requisicao` no corpo.

### Endpoints atuais

| Rota | O que faz |
|---|---|
| `GET /api/v1/health` | Liveness: o processo está no ar. Não toca o banco |
| `POST /api/v1/auth/entrar` | `{login, senha, dispositivo?}` → `{token, expira_em, usuario: {id, nome, login, papel}}`. O token vem uma vez só e vale 30 dias. Recusa sempre com o mesmo `401`; tentativas demais do mesmo IP, `429` com `Retry-After` |
| `POST /api/v1/auth/sair` · `GET /api/v1/auth/eu` | Encerra a sessão deste token (`204`) / quem está logado |
| `PUT /api/v1/auth/senha` | `{senha_atual, senha_nova}` (mínimo 8): troca a própria senha e encerra as sessões dos outros aparelhos (`204`); senha atual errada é `400` |
| `GET /api/v1/usuarios` · `POST /api/v1/usuarios` | Usuários com `ativo` e `bloqueado_ate` / cadastra (`nome`, `login`, `senha`, `papel`); login repetido `409` |
| `PUT /api/v1/usuarios/{id}` | `nome`, `papel`, `ativo` (o que não vier fica). Desativar derruba as sessões; o último dono ativo não sai (`409`) |
| `PUT /api/v1/usuarios/{id}/senha` | Redefine a senha (`senha_nova`), derruba as sessões e desfaz o bloqueio (`204`) |
| `GET /api/v1/ready` | Readiness: `200` com o banco respondendo, `503` sem ele |
| `GET /api/v1/insumos` | Insumos (filtros opcionais: `categoria_id`, `busca` no nome sem diferenciar maiúsculas nem acentos, `gravidade`, `com_alerta`) com a `categoria`, estoque atual, `custo_medio`, `valor_em_estoque`, `em_pedido` e `chegada_prevista` (o que foi pedido e não chegou) e a análise de hoje (alertas com `valor` em R$, reposição com `custo_estimado` e descontado o que está a caminho, limitações) |
| `GET /api/v1/insumos/{id}` | Um insumo com a análise, o saldo no fim de cada dia com movimentação (`historico`), as movimentações e o preço médio pago a cada fornecedor (`precos_por_fornecedor`, o mais barato primeiro) |
| `POST /api/v1/insumos` · `PUT /api/v1/insumos/{id}` | Cadastra / altera insumo (nome, unidade, mínimo, prazo de reposição e, opcionais, `embalagem`, `pedido_minimo`, `carencia_dias` e `categoria_id`). `409` para nome repetido, `422` para categoria inexistente. No `PUT`, embalagem, pedido mínimo, carência e categoria ausentes ficam como estão |
| `GET /api/v1/categorias` · `POST /api/v1/categorias` | As categorias pelo nome, com quantos `insumos` cada uma tem / cadastra (`nome`). `409` para nome repetido |
| `PUT /api/v1/categorias/{id}` · `DELETE /api/v1/categorias/{id}` | Renomeia / remove a categoria sem insumo; com algum, `409` dizendo quantos |
| `GET /api/v1/relatorios/periodo` | Por `mes`, `semana` ou `dia`, de `desde` a `ate` (padrão: os últimos 12 meses), com filtros `categoria_id`, `insumo_id`, `talhao_id` e `fornecedor_id`: cada período (zerado se vazio) com o consumo por insumo, o gasto, as perdas e os totais por categoria e por fornecedor; o `total` e as `limitacoes`. `422` para período invertido ou mais de 400 períodos |
| `DELETE /api/v1/insumos/{id}` | Remove o insumo cadastrado por engano, com as movimentações dele. `409` se ele foi aplicado em algum talhão: a rastreabilidade e a carência não somem com ele (remova antes as aplicações) |
| `GET /api/v1/movimentacoes` | Entradas e saídas, as mais recentes primeiro (no mesmo dia, pelo id). Filtros opcionais: `insumo_id`, `tipo`, `motivo` (`nenhum` = retirada para uso ou compra), `categoria_id`, `talhao_id`, `fornecedor_id`, `usuario_id`, `desde`/`ate` e `busca`; página com `limite` e `deslocamento`, e o total no cabeçalho `X-Total-Count`; cada uma com `usuario_id` e `lancado_por` (quem lançou; `null` sem login), `fornecedor_id` e `comprado_de` (de quem foi a compra) e `item_do_pedido_id` (o pedido que ela recebeu) |
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
| `GET /api/v1/relatorio.xlsx` | Relatório do estoque em Excel, com as abas Pedidos (o que falta chegar), Talhões e Por mês (os últimos 12 meses em reais). A aba Movimentações tem o formato da importação (com o talhão de cada aplicação e o fornecedor de cada compra): é também a cópia de segurança, e volta pela mesma tela |
| `GET /api/v1/auditoria` | Só o dono, sempre com login: os eventos de auditoria, os mais recentes primeiro (`id`, `ocorrido_em`, `usuario_id`, `feito_por`, `acao`, `entidade`, `entidade_id`, `dados`, `origem`, `ip`, `dispositivo`). Filtros: `acao` (código ou grupo; desconhecida, `422`), `usuario_id`, `entidade`, `entidade_id`, `desde`, `ate`; página com `limite` e `deslocamento`, total em `X-Total-Count` |
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

**Para a trilha de auditoria** (seção 2, "Trilha de auditoria"), uma tela só do dono, escondida
do funcionário: a lista de `GET /auditoria` com quando, quem (`feito_por`; vazio é "sistema" ou
"login recusado"), a ação traduzida pelo código, o aparelho e o IP, com o filtro por grupo de
ação, por usuário e por período, e as páginas pelo `X-Total-Count`. Ao abrir um evento, mostrar
`dados`: o conteúdo do que foi apagado (na movimentação removida, um botão "lançar de novo"
pode preencher o formulário com ele) ou o antes e o depois. O app não precisa de nada: o que o
funcionário faz no campo não entra na trilha, e ele não a lê.

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
com `--reload`) e `web` (Node 24 rodando o Vite). Ao subir, a API aplica `alembic upgrade head`
e garante o papel da aplicação, as duas coisas como o dono do banco, e só então sobe o uvicorn
com o papel da aplicação (`backend/docker/entrypoint.sh`; ver "Banco: papéis e tempos-limite");
a espera pelo banco é o `healthcheck` do compose.

O Vite do container usa **polling** para perceber arquivos alterados (`VITE_POLLING` no
compose): no Docker Desktop do Windows, o código montado do host não gera eventos de arquivo
dentro do container, e sem isso o Vite serve a versão antiga até reiniciar.

Configuração por `.env` na raiz (modelo em `.env.example`). Variáveis obrigatórias sem default:
`ENVIRONMENT` e `DATABASE_URL` (montada pelo compose a partir de `APP_DB_USER`,
`APP_DB_PASSWORD` e `POSTGRES_DB`; a `MIGRATIONS_DATABASE_URL`, a partir de `POSTGRES_*`). `AUTENTICACAO`
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
| Multi-tenant com RLS, roles `hub_owner`/`hub_api` | Sem RLS; os dois papéis, sim (o dono, das migrations, e o da aplicação, só com DML) | Não há múltiplos clientes isolados no escopo do desafio; mas a API com poder de dono do cluster seria risco de qualquer jeito |
| SQLAlchemy **async** + asyncpg/psycopg | SQLAlchemy **síncrono** + psycopg 3 | A análise e a leitura de planilhas são CPU-bound e síncronas; rotas `def` rodam em threadpool |
| Alembic sem autogenerate (`target_metadata=None`) | Autogenerate ligado, migration **revisada** | Lá o motivo era RLS invisível ao autogenerate; aqui não existe |
| Vuetify | Tailwind CSS v4 | Stack definida para o projeto |
| openapi-fetch + TanStack Query | Axios + Pinia | Stack definida para o projeto |
| Tipos TS gerados do OpenAPI | Escritos à mão (por ora) | Poucos recursos; geração entra quando a API crescer |
| Dois stacks compose + rede `edge` | Um compose só | Sem serviços internos (MinIO, Redis, worker) a isolar |
| MinIO, Redis, worker, ClamAV | Não entrou | Nenhum requisito do CampoCerto pede, por ora |
| Rate-limit por IP | Na memória do processo (login e escritas), com a interface pronta para trocar | Um uvicorn só no compose; sem Redis no stack |
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

7. **Categorias, filtros e relatório nas telas.** A API já tem as categorias, os filtros, a busca
   e a paginação das listas e o relatório por período (seção 2, "Categorias, filtros e relatório
   por período"); o site e o app ainda não os usam. O site precisa de: a escolha da categoria no
   cadastro do insumo (`GET /categorias`) e uma tela simples de Categorias para o dono; os filtros
   e a caixa de busca nas listas de Insumos e Movimentações (os parâmetros acima), com a
   paginação lendo `X-Total-Count`; e uma tela de Relatório com o gráfico mês a mês (gasto,
   consumo e perdas em reais), as tabelas por categoria e por fornecedor e as `limitacoes`. O app
   precisa, no mínimo, da busca e do filtro por categoria na lista de insumos; nada muda na fila
   offline. Sem isso, nada quebra: sem os parâmetros novos, as respostas são as de antes.
8. **O `429` e o código do pedido nas telas.** A API limita tentativas de login e escritas por
   IP e põe `X-Request-ID` em toda resposta (seção 2, "Blindagem da API"). O `ApiError` do site
   e o do app já mostram o `detail` quando é frase, e o `429`, o `500` e o `503` agora trazem
   uma: nada quebra. Falta: a fila do app não reenviar antes do `Retry-After` quando receber
   `429`, e as telas mostrarem o `id_da_requisicao` do `500` e do `503` ("informe ao suporte o
   código ..."). O app pode mandar o próprio `X-Request-ID` (o uuid do envio) para o mesmo
   código aparecer no celular e no log do servidor.

Decididas desde a versão anterior deste documento: a autenticação existe (dono e funcionário,
obrigatória em produção, seção 2); a importação de planilha existe (Excel e
CSV, seção 2); o ECharts entrou com o gráfico do insumo; o Pandas não entrou, porque nem o motor de
análise nem a importação precisaram; o `openpyxl` entrou para ler e gerar `.xlsx`.
