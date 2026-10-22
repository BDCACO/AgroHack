# Roteiro da apresentação

Demonstração de 5 a 7 minutos com a fazenda fictícia. A ideia que costura tudo: **cada alerta
mostra a conta que o justifica e o que a conta não sabe.**

## Antes de começar (no dia)

1. `make up` e, com o stack no ar, `make demo` **no próprio dia da apresentação**: as datas da fazenda
   são relativas ao dia da carga, e o roteiro abaixo depende disso.
2. Abrir http://localhost:5173 e conferir no Painel: 2 urgentes, 3 de atenção, 2 para observar.
3. Para mostrar no celular, abrir `http://<IP do notebook>:5173` (a porta do front fica aberta na
   rede local). O botão do WhatsApp precisa do app no celular ou do WhatsApp Web logado.
4. Ter à mão `docs/exemplos/planilha-com-erros.csv` e o Excel (ou o LibreOffice) instalado,
   para abrir a planilha modelo.

## O que cada insumo da demonstração mostra

| Insumo | Alerta | Para falar |
|---|---|---|
| Ureia agrícola | Risco de falta + abaixo do mínimo | Consumo acelerou na cobertura; o estoque dura menos que o prazo de entrega → pedir hoje, em sacos de 50 kg fechados e com o custo da compra |
| Ivermectina 1% | Lote vencido | Lote antigo vencido ainda na prateleira, o novo em dia; o alerta diz quanto dinheiro venceu |
| Glifosato 480 | Vencimento próximo | Lote vence em 20 dias e ainda tem produto |
| Sal mineral 80P | Consumo incomum | Última semana muito acima da média das 12 anteriores |
| Calcário dolomítico | Excesso | Estoque para anos no ritmo atual: o alerta diz quanto capital está parado, em reais |
| Fungicida azoxistrobina | Baixa movimentação | Ninguém retira há mais de 3 meses |
| Semente de milho híbrido | Nenhum | Contraste: o que está em dia não grita |

## Roteiro

1. **O problema (30 s).** O produtor anota compras e retiradas, mas a anotação não avisa quando
   o adubo vai faltar ou o remédio vai vencer.
2. **Painel.** O resumo por gravidade e a lista de alertas. Ler em voz alta a justificativa do
   risco de falta da ureia: a conta está ali, com os números.
3. **Página da ureia** (clicar no nome). O gráfico: o consumo triplicou nos últimos três meses
   (adubação de cobertura), a última compra já foi quase toda usada, e o tracejado chega a zero
   em uns 8 dias ("dura cerca de 8 dias"), com entrega em 10. Por isso é urgente. A reposição
   diz quanto pedir e por quê: a conta dá 662 kg, mas a ureia vem em sacos de 50 kg, então são
   14 sacos (700 kg), e diz quanto a compra custa pelo custo médio das duas últimas compras.
4. **Limitações.** Na mesma página: o que a conta não sabe (sazonalidade). Nos outros insumos,
   sem embalagem cadastrada, a limitação diz que a sugestão não considera embalagem: o sistema
   diz só o que falta. Mostrar que ele é honesto sobre isso é diferencial.
5. **Lista de compras e relatório.** Voltar ao Painel → "Enviar pelo WhatsApp": a lista sai
   pronta para a revenda. Depois, "Baixar relatório (Excel)" e abrir: os alertas nas cores da
   tela, a reposição com o "pedir hoje" em destaque e o custo da compra, e a situação de cada
   insumo com o valor em estoque, para levar ao agrônomo ou ao banco. O Resumo traz o valor do
   estoque em reais. A última aba é a cópia de segurança das movimentações, com os preços.
6. **Importar planilha.** Em Importar dados, baixar a **planilha modelo (Excel)** e abri-la:
   cabeçalho formatado, listas de escolha com os insumos da fazenda, aba de instruções e um
   exemplo. Preencher duas linhas ao vivo (uma compra de um insumo novo e uma retirada) e
   importar: a prévia mostra quanto entra e sai de cada insumo antes de gravar. Depois, escolher
   `planilha-com-erros.csv`: nada é gravado, e cada erro diz a linha e o que corrigir (data que
   não existe, "dez" no lugar de 10, unidade diferente da cadastrada, insumo novo sem unidade).
7. **Lançar uma movimentação** (página da ureia → "Lançar movimentação"): uma entrada de 700 kg
   com a data de hoje, e os alertas da ureia somem do Painel na hora.
8. **Fechamento.** O que vem depois: acesso por usuário, sazonalidade da safra no consumo,
   e o resumo em reais (valor em estoque, perdas, compras do mês) nas telas do site e do app.

Depois da apresentação, `make demo-limpar` apaga a fazenda fictícia. Os insumos que vieram da
planilha modelo não são de demonstração: remova-os pela página de cada um.
