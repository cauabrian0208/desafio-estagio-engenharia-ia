# Decisões Técnicas

Este documento registra as principais escolhas de arquitetura, os trade-offs
assumidos, as limitações da solução e o que eu evoluiria com mais tempo.

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

Isso simplificaria parte do código, mas aumentaria o risco de erros numéricos,
resultados não reproduzíveis, maior consumo de tokens e dificuldade de
auditoria.

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
descartaria informações financeiras ainda úteis. Por isso, optei por preservar
esses registros quando possível.

---

## 3. Regras como mecanismo de triagem

As regras determinísticas foram tratadas como sinais de priorização e não como
comprovação de lavagem de dinheiro, fraude ou outro ilícito.

Isso é importante porque as regras foram propositalmente construídas com poucos
critérios e podem produzir falsos positivos.

No confronto com o agente, também foi necessário criar uma classificação
determinística de risco:

- baixo: nenhum evento;
- médio: um evento;
- alto: dois ou mais eventos ou ocorrência das duas tipologias.

Esse critério existe apenas para permitir a comparação solicitada no desafio e
não representa uma metodologia real de classificação de risco bancário.

Para o ranking do Top 10, cada operação marcada pelas regras é contabilizada
como uma sinalização. No confronto de risco, operações de fracionamento do mesmo
cliente e da mesma data são consolidadas como um único evento, pois fazem parte
do mesmo episódio.

---

## 4. Prompts e controle de inferências

No Nível 1 foram comparadas duas estratégias de prompt.

A abordagem com instruções mais restritivas apresentou melhor controle sobre a
resposta e foi usada como referência no agente do Nível 2.

O agente foi instruído a:

- utilizar somente as evidências disponíveis;
- não inventar contexto;
- não realizar cálculos que deveriam ser feitos pelas ferramentas;
- tratar flags como sinais de triagem;
- evitar afirmações sobre intenção criminosa sem evidência;
- manter recomendações proporcionais e sujeitas à revisão humana.

Mesmo com essas restrições, o lote mostrou que o LLM ainda pode produzir
inferências excessivas. No caso CLI-013, por exemplo, a classificação de risco
foi considerada razoável, mas parte da justificativa extrapolou o que os dados
permitiam afirmar.

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

Isso seria mais previsível, porém transformaria o agente em um fluxo praticamente
fixo e enviaria informações desnecessárias ao modelo.

A seleção dinâmica reduz dados enviados, tokens e chamadas desnecessárias e
também demonstra comportamento realmente orientado por ferramentas.

A desvantagem é que a qualidade da investigação passa a depender também da
decisão do modelo sobre quais ferramentas consultar.

---

## 6. Execução em lote, custo e rate limit

Tokens, custo estimado e latência são registrados em cada chamada ao modelo e
posteriormente analisados com pandas.

Durante o lote ocorreram limites temporários da API. Para impedir a interrupção
do processamento, foi implementado retry com espera antes de novas tentativas.

Também foi utilizada uma pausa entre alguns clientes.

### Trade-off

O retry aumenta o tempo total de processamento, mas é preferível a perder uma
execução longa no meio do lote.

Em produção, eu substituiria essa solução simples por controle centralizado de
rate limit, filas e políticas de retry com backoff.

---

## 7. Confronto entre regras e agente

A comparação entre as regras determinísticas e o agente não foi tratada como uma
competição em que uma das abordagens precisa sempre estar correta.

As regras são objetivas e reproduzíveis, mas possuem pouco contexto.

O agente consegue considerar evidências adicionais, porém continua sujeito a
inferências inconsistentes.

Por isso, as divergências foram analisadas individualmente.

Em alguns clientes, o agente produziu uma priorização mais proporcional. Em
outros, tanto a regra quanto o agente pareceram extremos e uma classificação
intermediária seria mais adequada.

Essa análise reforçou a escolha de utilizar o LLM como apoio ao analista, e não
como mecanismo automático de decisão final.

---

## 8. Escolha da Trilha C no Nível 3

Para o Nível 3 escolhi a Trilha C e implementei uma interface conversacional com
Streamlit.

Considerei que essa trilha aproveitaria melhor os resultados produzidos nos
níveis anteriores e permitiria demonstrar um fluxo próximo ao de um analista
utilizando a solução.

A interface permite consultar um cliente, gerar explicações e pareceres,
comparar clientes e continuar a conversa utilizando memória durante a sessão.

A memória é separada conforme o contexto da análise para evitar que uma conversa
sobre um cliente seja reutilizada indevidamente ao trocar para outro caso.

### Trade-off

A memória existe somente na sessão do Streamlit e não é persistente.

Isso simplifica a implementação e é suficiente para o desafio, mas uma aplicação
real precisaria armazenar sessões e decisões de forma auditável.

---

## 9. Segurança e credenciais

A chave da API não fica no código.

Ela é carregada a partir de `.env`, enquanto o repositório disponibiliza apenas
`.env.example`.

O `.env` é ignorado pelo Git.

Em um ambiente real, eu substituiria o arquivo local por um serviço próprio de
gestão de secrets e adicionaria controle de acesso e auditoria.

---

## 10. Limitações

A solução utiliza dados fictícios e uma quantidade pequena de operações.

Ela não possui informações suficientes para representar um sistema real de PLD,
como perfil cadastral completo, atividade econômica, histórico de longo prazo,
relações entre contas, informações de beneficiários, jurisdições e listas
restritivas.

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

Por isso, as classificações devem ser interpretadas como apoio à triagem humana.

---

## 11. O que faria com mais tempo

### Avaliação do LLM

Criaria um conjunto fixo de casos de teste com resultados esperados e executaria
avaliações periódicas para comparar prompts e modelos.

Validaria principalmente aderência às evidências, estabilidade do risco,
ocorrência de informações inventadas e qualidade das recomendações.

### Persistência

Utilizaria PostgreSQL ou outra base relacional para armazenar investigações,
pareceres, conversas, decisões humanas e métricas.

Isso permitiria histórico, auditoria e continuidade das análises.

### Observabilidade

Centralizaria logs de chamadas, tokens, custo, latência, ferramentas utilizadas,
retries, versões de prompt e versões de modelo.

Também criaria alertas para aumento de custo, falhas e mudanças relevantes no
comportamento do agente.

### Segurança

Adicionaria autenticação, autorização por perfil, gestão centralizada de
segredos, sanitização de entradas, proteção contra prompt injection e políticas
de retenção de dados.

### Processamento em escala

Separaria ingestão, motor de regras, serviço de ferramentas, agente e interface.

O processamento do lote passaria a utilizar filas, workers e controle de rate
limit, em vez de pausas realizadas durante uma execução local.

---

## Conclusão

A principal decisão do projeto foi manter evidências objetivas e cálculos
auditáveis fora do LLM.

As regras determinísticas oferecem consistência e rastreabilidade, enquanto o
agente adiciona contexto e flexibilidade.

A interface coloca essas duas abordagens à disposição de um analista humano.

A solução não tenta automatizar uma decisão final de PLD. O objetivo é demonstrar
como regras, ferramentas e modelos de linguagem podem ser combinados para apoiar
uma triagem mais contextualizada e ainda manter espaço para revisão humana.