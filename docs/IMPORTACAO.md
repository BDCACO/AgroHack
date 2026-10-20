# Importar planilhas

Guia para carregar no CampoCerto o histórico de compras e retiradas que já está numa planilha,
sem relançar tudo pela tela.

## Em resumo

1. Em **Importar dados**, baixe a **planilha modelo (Excel)**.
2. Preencha a aba **Movimentações**: uma linha por compra que chegou ou retirada do galpão.
3. Volte a **Importar dados** e escolha o arquivo.
4. Confira o resumo — quanto entra e sai de cada insumo — e clique em **Importar**.

Nada é gravado antes do passo 4. Se a planilha tiver qualquer erro, **nada** é gravado, e a tela
diz a linha e o que corrigir.

## A planilha modelo

É gerada na hora do download, com quatro abas:

| Aba | Para quê |
|---|---|
| **Movimentações** | A que você preenche — e a única que a importação lê. Títulos na linha 1, datas em DD/MM/AAAA e listas de escolha para insumo, unidade e tipo. O próprio Excel avisa se a data for futura, se o tipo não for entrada ou saída e se a quantidade não for maior que zero. |
| **Como preencher** | As instruções, resumidas. |
| **Exemplo** | Três linhas preenchidas do jeito certo. |
| **Insumos cadastrados** | Os insumos que já estão no CampoCerto, com a unidade de cada um. É de onde vem a lista de escolha da coluna `insumo`: depois de cadastrar outros, baixe o modelo de novo. |

Passe o mouse sobre o título de uma coluna para ver a explicação dela.

## As colunas

| Coluna | Obrigatória | Como preencher | Exemplo |
|---|---|---|---|
| `data` | Sim | Dia em que a compra chegou ou em que o produto saiu do galpão. Não pode ser futura. | 05/03/2026 |
| `insumo` | Sim | Nome do produto. Maiúsculas não importam: "ureia agrícola" é o mesmo que "Ureia agrícola". Um nome que não existe vira insumo novo. | Ureia agrícola |
| `unidade` | Só para insumo novo | kg, L, t, sc, dose, un… Para um insumo já cadastrado, deixe em branco ou repita a do cadastro. | kg |
| `tipo` | Sim | `entrada` (compra que chegou) ou `saída` (retirada do galpão). Também valem `compra` e `retirada`. | saída |
| `quantidade` | Sim | Maior que zero, na unidade do insumo. | 25,5 |
| `validade` | Não | Validade do lote, só em entradas. Em branco se o produto não vence. | 30/06/2027 |

Pode haver outras colunas — observação, fornecedor, nota fiscal —, desde que tenham título na
linha 1: a importação ignora as que não conhece.

## Excel ou CSV

| Formato | Como fica |
|---|---|
| **.xlsx** (Excel) | O recomendado. Datas e números chegam como o Excel guarda, sem dúvida sobre vírgula ou ponto. Só a primeira aba é lida. |
| **.csv** | Também vale, separado por ponto e vírgula (o "CSV" do Excel em português) ou por vírgula, com acentos em UTF-8 ou no formato do Excel antigo (Windows-1252). Há um modelo em CSV na mesma tela. |
| **.xls** (Excel antigo) | Não é aceito. Abra no Excel e salve como **Pasta de Trabalho do Excel (.xlsx)**. |

### Números escritos como texto

No CSV — e numa célula de texto do Excel —, `25.500` tanto pode ser vinte e cinco e meio quanto
vinte e cinco mil. O CampoCerto decide olhando a planilha inteira, não célula a célula:

| Na planilha | Lido como | Por quê |
|---|---|---|
| `25,5` | 25,5 | vírgula seguida de uma casa só pode ser decimal |
| `1.234,5` | 1.234,5 | vírgula depois do ponto: o ponto é de milhar |
| `0.250` | 0,25 | ninguém escreve `0.250` querendo dizer 250 |
| `1.000`, num CSV separado por `;` e sem outra pista | 1.000 (mil) | o costume do Excel em português |
| `25.500`, num CSV separado por `,` e sem outra pista | 25,5 | o costume internacional |

Uma planilha que mistura vírgula e ponto decimal é recusada. De todo modo, **confira os totais na
prévia**: um número lido errado aparece ali, antes de gravar.

## O que a importação faz — e o que não faz

- **Tudo ou nada.** Com um erro sequer, nada entra. Meia planilha importada deixaria o estoque
  errado sem ninguém perceber.
- **Soma, não substitui.** Cada importação acrescenta ao que já está no sistema. Importar a mesma
  planilha duas vezes duplica o consumo; por isso a prévia avisa quando há linhas iguais a
  movimentações já lançadas.
- **Insumo novo entra sem mínimo nem prazo de entrega.** Complete os dois na tela de Insumos: sem
  o mínimo não há alerta de estoque baixo, e sem o prazo a análise supõe 15 dias.
- **O estoque é a soma das movimentações.** Lance como entrada o que já estava no galpão no
  começo do período; sem isso, as saídas deixam o estoque negativo.
- **Limites:** 5 MB e 50.000 movimentações por arquivo. Planilha maior: divida por ano.

## Erros comuns

| A tela diz | O que fazer |
|---|---|
| Faltam as colunas: … | A linha 1 precisa ter os títulos. Use a planilha modelo. |
| data "31/02/2026" inválida | Corrija a data (DD/MM/AAAA). Se aparece um número no lugar da data, a célula está sem formato de data: formate-a como data. |
| data no futuro | Ano digitado errado? (2062 por 2026) |
| tipo "devolução" desconhecido | Use `entrada` ou `saída`. Devolução ao fornecedor é uma saída. |
| quantidade "dez" não é um número | Escreva o número: 10. |
| "Adubo X" não está cadastrado; informe a unidade | Insumo novo precisa da unidade na linha. |
| "Ureia" já está cadastrado em kg, não em sc | Converta para a unidade do cadastro (10 sacas de 50 kg = 500 kg). |
| há mais de um insumo cadastrado como "ureia" | Renomeie um deles na tela de Insumos. |
| validade só se informa numa entrada | Apague a validade da linha de saída. |
| há valores em colunas sem título | Dê um título à coluna ou apague os valores. |
| 6 colunas, mas o cabeçalho tem 5 | CSV separado por vírgula com vírgula decimal: separe por ponto e vírgula ou ponha o número entre aspas. |
| aspa (") sem fechar | Uma célula começa com aspa e não termina com outra: corrija e salve de novo. |
| Quantidades com vírgula decimal e com ponto decimal na mesma planilha | Use um formato só em toda a coluna `quantidade`. |
| Não deu para abrir a planilha do Excel | Abra o arquivo no Excel, salve como .xlsx e tente de novo. |

A planilha `docs/exemplos/planilha-com-erros.csv` mostra vários desses erros de uma vez — útil
para ver como a tela os apresenta.
