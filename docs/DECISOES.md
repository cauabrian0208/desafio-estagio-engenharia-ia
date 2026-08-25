# Decisões Técnicas

Este documento registra as principais escolhas que fiz durante o desenvolvimento,
os trade-offs assumidos, as limitações da solução e o que eu evoluiria com mais
tempo.

---

## 1. Regras determinísticas separadas do LLM

A principal decisão de arquitetura foi manter cálculos e regras fora do modelo
de linguagem.

Soma, contagem, mediana, conversão de moeda, fracionamento e identificação de
valores atípicos são calculados com Python e pandas. O LLM recebe essas
evidências já estruturadas e é utilizado somente para interpretação e geração
do parecer.

### Trade-off

Uma alternativa seria enviar todas as operações diretamente ao LLM e pedir que
ele identificasse os padrões.

Isso simplificaria parte do código, mas aumentaria o risco de:

- erros numéricos;
- resultados não reproduzíveis;
- maior consumo de tokens;
- dificuldade de auditoria;
- mistura entre cálculo e interpretação.

Preferi uma arquitetura híbrida porque as regras ficam objetivas e
reproduzíveis, enquanto o modelo é utilizado onde interpretação textual é mais
útil.

---

## 2. Tratamento dos dados

Registros duplicados são removidos pelo identificador da operação.

Datas ausentes são preservadas como valores nulos. Dessa forma, a operação ainda
pode ser utilizada em análises que não dependem da dimensão temporal, mas não
participa de regras que exigem agrupamento por data.

Valores em USD são convertidos para BRL exclusivamente pela taxa disponibilizada
nos próprios dados.

### Trade-off

Excluir todas as operações sem data simplificaria o processamento, mas também
descartaria informações financeiras ainda úteis.

Por isso, optei por preservar esses registros quando possível.

---

## 3. Regras como mecanismo de triagem

As regras determinísticas foram tratadas como sinais de priorização e não como
comprovação de lavagem de dinheiro, fraude ou outro ilícito.

Isso é importante porque as regras foram propositalmente construídas com poucos
critérios e podem produzir falsos positivos.

No confronto com o agente, também foi necessário criar uma classificação
determinística de risco:

- **baixo:** nenhum evento;
- **médio:** um evento;
- **alto:** dois ou mais eventos ou ocorrência das duas tipologias.

Esse critério existe apenas para permitir a comparação solicitada no desafio e
não representa uma metodologia real de classificação de risco bancário.

Para o ranking do Top 10, cada operação marcada pelas regras é contabilizada
como uma sinalização.

No confronto de risco, operações de fracionamento do mesmo cliente e da mesma
data são consolidadas como um único evento, pois fazem parte do mesmo episódio.

---

## 4. Prompts e controle de inferências

No Nível 1 foram comparadas duas estratégias de prompt.

A primeira versão era mais simples, enquanto a segunda adicionava restrições
explícitas para limitar a resposta às evidências disponíveis.

A abordagem mais restritiva apresentou melhor controle sobre a resposta e foi
usada como referência no agente do Nível 2.

O agente foi instruído a:

- utilizar somente as evidências disponíveis;
- não inventar contexto;
- não realizar cálculos que deveriam ser feitos pelas ferramentas;
- tratar flags como sinais de triagem;
- evitar afirmações sobre intenção criminosa sem evidência;
- manter recomendações proporcionais;
- deixar a decisão final sujeita à revisão humana.

Mesmo com essas restrições, o lote mostrou que o LLM ainda pode produzir
inferências excessivas.

No caso `CLI-013`, por exemplo, a classificação de risco foi considerada
razoável, mas parte da justificativa extrapolou o que os dados permitiam afirmar.

Essa ocorrência foi mantida como uma limitação da solução, em vez de considerar
a saída do modelo automaticamente correta.

---

## 5. Agente com seleção dinâmica de ferramentas

O agente do Nível 2 possui quatro ferramentas:

- `historico_cliente`
- `operacoes_do_dia`
- `perfil_canal`
- `operacoes_sinalizadas`

A decisão de quais ferramentas utilizar é feita dinamicamente pelo modelo.

### Trade-off

Uma alternativa seria executar todas as ferramentas para todos os clientes antes
de consultar o LLM.

Isso seria mais previsível, porém transformaria o agente em um fluxo
praticamente fixo e enviaria informações desnecessárias ao modelo.

A seleção dinâmica reduz dados enviados, tokens e chamadas desnecessárias e
também demonstra comportamento realmente orientado por ferramentas.

A desvantagem é que a qualidade da investigação passa a depender também da
decisão do modelo sobre quais ferramentas consultar.

Durante a execução do lote foi possível observar essa diferença: alguns clientes
exigiram consulta às operações de um dia específico, enquanto outros foram
analisados apenas a partir das operações sinalizadas e do histórico agregado.

---

## 6. Execução em lote, custo e rate limit

Tokens, custo estimado e latência são registrados em cada chamada ao modelo e
posteriormente analisados com pandas.

Durante o lote ocorreram limites temporários da API.

Para impedir a interrupção do processamento, foi implementado retry com espera
antes de novas tentativas.

Também foi utilizada uma pausa entre alguns clientes durante a execução.

### Trade-off

O retry aumenta o tempo total do processamento, mas é preferível a perder uma
execução longa no meio do lote.

Em produção, eu substituiria essa solução simples por:

- controle centralizado de rate limit;
- filas;
- workers;
- políticas de retry;
- cache quando aplicável.

---

## 7. Confronto entre regras e agente

A comparação entre as regras determinísticas e o agente não foi tratada como uma
competição em que uma das abordagens precisa sempre estar correta.

As regras são objetivas e reproduzíveis, mas possuem pouco contexto.

O agente consegue considerar evidências adicionais, porém continua sujeito a
inferências inconsistentes.

Por isso, as divergências foram analisadas individualmente.

Em alguns clientes, o agente produziu uma priorização mais proporcional.

Em outros, tanto a classificação determinística quanto a classificação do
agente pareceram extremas e uma classificação intermediária seria mais
adequada.

Também houve caso em que a classificação do agente parecia adequada, mas a
justificativa introduziu uma inferência que não estava sustentada pelos dados.

A análise qualitativa das seis divergências foi escrita especificamente para
este lote e não é recalculada automaticamente caso os dados sejam alterados.

Essa foi uma decisão consciente, porque a parte solicitada no desafio envolve
justamente avaliar as divergências e discutir, caso a caso, qual interpretação
parece mais adequada.

Em uma solução real, essa avaliação teria participação formal de um analista e
seu resultado seria armazenado como decisão humana auditável.

O confronto reforçou a escolha de utilizar o LLM como apoio ao analista, e não
como mecanismo automático de decisão final.

---

## 8. Escolha da Trilha C no Nível 3

Para o Nível 3 escolhi a **Trilha C — Interface Conversacional** e implementei
uma aplicação com Streamlit.

Considerei que essa trilha aproveitaria melhor os resultados produzidos nos
níveis anteriores e permitiria demonstrar um fluxo próximo ao de um analista
utilizando a solução.

A interface permite:

- consultar um cliente;
- visualizar risco do agente e risco determinístico;
- consultar a análise estruturada;
- pedir uma explicação do caso;
- gerar um parecer resumido;
- comparar dois clientes;
- realizar perguntas adicionais;
- continuar a conversa utilizando memória durante a sessão.

A memória é separada conforme o contexto da análise para evitar que uma conversa
sobre um cliente seja reutilizada indevidamente ao trocar para outro caso.

Também há um contexto separado para comparações entre clientes.

### Trade-off

A memória existe somente durante a sessão do Streamlit e não é persistente.

Isso simplifica a implementação e é suficiente para o desafio, mas uma aplicação
real precisaria armazenar sessões e decisões de forma auditável.

---

## 9. Segurança e credenciais

A chave da API não fica no código.

Ela é carregada a partir de uma variável de ambiente configurada no arquivo
`.env`.

O repositório disponibiliza apenas:

```text
.env.example
```

sem valor real de credencial.

O `.env` é ignorado pelo Git.

Durante o desenvolvimento, o tratamento de credenciais também foi revisado para
evitar que uma chave real fosse enviada ao repositório.

Em um ambiente de produção, eu substituiria o arquivo local por um serviço
próprio de gestão de secrets e adicionaria:

- autenticação;
- autorização;
- controle de acesso;
- auditoria.

---

## 10. Limitações

A solução utiliza dados fictícios e uma quantidade pequena de operações.

Ela não possui informações suficientes para representar um sistema real de PLD,
como:

- perfil cadastral completo;
- atividade econômica;
- histórico de longo prazo;
- relações entre contas;
- informações de beneficiários;
- jurisdições;
- listas restritivas;
- comportamento esperado do cliente.

Também não foram implementados:

- autenticação e autorização;
- banco de dados;
- persistência das conversas;
- observabilidade centralizada;
- testes automáticos de regressão dos prompts;
- avaliação automatizada da qualidade do LLM;
- proteção completa contra prompt injection;
- integração com sistemas bancários reais.

Além disso, respostas do LLM podem variar e uma justificativa aparentemente
coerente não garante que todas as inferências estejam sustentadas pelos dados.

Mesmo com instruções explícitas para não realizar cálculos ou criar informações,
o modelo ainda pode produzir pequenas derivações a partir das evidências
recebidas.

Por isso, as classificações devem ser interpretadas como apoio à triagem humana.

---

## 11. O que faria com mais tempo

Como os requisitos principais do desafio foram implementados, as evoluções abaixo
são melhorias que eu faria pensando em uma solução mais próxima de produção.

### Avaliação do LLM

Criaria um conjunto fixo de casos de teste com exemplos de diferentes tipos de
sinalização e respostas esperadas.

A avaliação seria executada sempre que houvesse mudança de prompt ou modelo.

Como ferramenta, poderia utilizar testes em Python com `pytest` e um conjunto
versionado de casos de avaliação.

Validaria principalmente:

- aderência às evidências fornecidas;
- estabilidade da classificação de risco;
- ocorrência de informações inventadas;
- qualidade e proporcionalidade das recomendações;
- consistência entre diferentes execuções.

Consideraria a melhoria válida se novas versões mantivessem ou aumentassem a
qualidade nesses casos sem aumentar de forma relevante erros ou custo.

---

### Persistência

Separaria o armazenamento da aplicação utilizando um banco relacional, como
PostgreSQL.

Seriam armazenados:

- investigações;
- pareceres;
- conversas;
- decisões tomadas pelo analista;
- métricas de execução;
- versão do prompt;
- versão do modelo.

A interface e o agente deixariam de depender apenas do estado em memória e
passariam a consultar essa camada de persistência.

Para validar, criaria testes de criação, consulta e recuperação de uma
investigação completa e verificaria se uma sessão poderia ser encerrada e
retomada sem perda de contexto.

---

### Observabilidade

Criaria uma camada centralizada de observabilidade para registrar:

- chamadas ao LLM;
- tokens;
- custo;
- latência;
- ferramentas utilizadas;
- erros;
- retries;
- versão do prompt;
- versão do modelo.

Uma possibilidade seria utilizar logs estruturados e uma ferramenta de
monitoramento como Grafana, associada a uma fonte de métricas.

Também criaria alertas para aumento inesperado de custo, latência ou taxa de
erros.

Validaria essa camada provocando erros e execuções controladas e verificando se
as métricas, logs e alertas correspondentes seriam registrados corretamente.

---

### Segurança

Em um cenário real, adicionaria:

- autenticação;
- autorização por perfil;
- gestão centralizada de segredos;
- sanitização de entradas;
- proteção contra prompt injection;
- políticas de retenção de dados;
- trilha de auditoria.

As credenciais deixariam de depender de um `.env` local e seriam obtidas por um
gerenciador de secrets da infraestrutura utilizada.

A validação incluiria testes com usuários de perfis diferentes, tentativas de
acesso não autorizado, entradas maliciosas e verificação de que informações
sensíveis não aparecem nos logs ou respostas do modelo.

---

### Processamento em escala

Separaria a solução em componentes independentes:

1. ingestão e limpeza;
2. motor de regras;
3. serviço de ferramentas;
4. agente;
5. armazenamento;
6. interface para analistas.

Para o processamento do lote, utilizaria uma fila de tarefas e workers em vez
de pausas dentro de uma única execução.

Dependendo da infraestrutura, uma opção seria utilizar uma fila como SQS ou
RabbitMQ com workers responsáveis pelas investigações.

Validaria a arquitetura com testes de carga, aumentando progressivamente a
quantidade de clientes e acompanhando tempo de processamento, erros, rate limit
e consumo da API.

---

### Human-in-the-loop

Em uma aplicação real, a resposta do agente não deveria encerrar o fluxo.

Criaria uma etapa formal em que o analista pudesse:

- aceitar ou rejeitar o parecer;
- alterar a classificação;
- registrar o motivo da decisão;
- solicitar uma investigação adicional.

Essas decisões seriam persistidas e associadas ao caso analisado.

Para validar esse fluxo, criaria casos de teste completos desde a sinalização
inicial até a decisão humana e verificaria se todas as ações ficariam
registradas e auditáveis.

Com dados suficientes, essas decisões humanas também poderiam formar um conjunto
de avaliação para medir se o agente está melhorando ao longo do tempo.

---

## Conclusão

A principal decisão do projeto foi manter evidências objetivas e cálculos
auditáveis fora do LLM.

As regras determinísticas oferecem consistência e rastreabilidade, enquanto o
agente adiciona contexto e flexibilidade.

O confronto mostrou que nenhuma das duas abordagens deve ser tratada como
verdade absoluta: regras simples podem gerar falsos positivos e o modelo pode
produzir interpretações que vão além das evidências.

A interface coloca essas informações à disposição de um analista humano.

A solução não tenta automatizar uma decisão final de PLD. O objetivo é
demonstrar como regras, ferramentas e modelos de linguagem podem ser combinados
para apoiar uma triagem mais contextualizada, mantendo a revisão humana como
parte essencial do processo.