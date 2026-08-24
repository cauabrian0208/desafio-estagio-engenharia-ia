# Decisões Técnicas

Este documento registra as principais decisões de arquitetura, trade-offs,
limitações e possíveis evoluções da solução desenvolvida para o desafio.

---

## 1. Separação entre regras determinísticas e LLM

Uma das principais decisões do projeto foi manter cálculos e regras
determinísticas separados da interpretação realizada pelo modelo de linguagem.

Operações como:

- soma;
- contagem;
- mediana;
- comparação com limites;
- identificação de fracionamento;
- detecção de valor atípico;

foram realizadas com Python e pandas.

O LLM foi utilizado somente depois que esses resultados já estavam calculados,
com a responsabilidade de interpretar as evidências e gerar um parecer textual.

### Trade-off

Uma alternativa seria enviar todo o conjunto de operações diretamente para o
LLM e pedir que ele detectasse padrões.

Essa abordagem seria mais simples de implementar, porém teria maior risco de:

- erros numéricos;
- resultados não reproduzíveis;
- maior consumo de tokens;
- dificuldade de auditoria;
- mistura entre cálculo e interpretação.

Por isso, foi adotada uma abordagem híbrida, em que pandas produz evidências
objetivas e o modelo atua sobre essas evidências.

---

## 2. Tratamento dos dados

Foram identificados problemas de qualidade nos dados, principalmente:

- registros duplicados;
- datas ausentes;
- valores em moedas diferentes.

Os registros duplicados foram removidos pelo identificador da operação.

As datas ausentes foram preservadas como valores nulos. Essas operações
continuaram válidas para análises que não dependiam de tempo, mas foram
excluídas de agrupamentos por data.

Os valores em USD foram convertidos para BRL utilizando exclusivamente a taxa
de câmbio fornecida no próprio arquivo.

### Trade-off

Uma alternativa seria remover completamente registros sem data.

Essa opção foi descartada porque eliminaria informações financeiras ainda
úteis para outras análises.

---

## 3. Regras determinísticas

Foram implementadas duas regras:

### Fracionamento

Um cliente é sinalizado quando realiza, na mesma data:

- três ou mais operações;
- soma superior a R$ 50.000;
- nenhuma operação isolada igual ou superior a R$ 20.000.

### Valor atípico

Uma operação é sinalizada quando seu valor em BRL é superior a cinco vezes a
mediana das operações daquele cliente.

A regra é aplicada apenas a clientes com quatro ou mais operações.

### Limitação

Essas regras foram utilizadas como mecanismos de triagem.

Elas não devem ser interpretadas como comprovação de lavagem de dinheiro ou
de qualquer comportamento ilícito.

---

## 4. Uso do LLM no Nível 1

Foram testadas duas versões de prompt.

A primeira versão fornecia instruções mais simples.

A segunda adicionava restrições explícitas para:

- utilizar somente os fatos disponíveis;
- não realizar novos cálculos;
- não inventar contexto;
- diferenciar comportamento atípico de comprovação de ilícito.

A segunda abordagem apresentou respostas mais objetivas e controladas.

Por isso, instruções semelhantes foram reutilizadas posteriormente no agente
do Nível 2.

---

## 5. Escolha do modelo

Foi utilizado o modelo:

`openai/gpt-oss-20b`

por meio da API da Groq.

A escolha foi baseada principalmente em:

- disponibilidade na camada gratuita utilizada durante o desafio;
- suporte a chamadas estruturadas;
- suporte a tool calling;
- velocidade de resposta;
- possibilidade de registrar tokens consumidos.

Inicialmente foi testado outro modelo da Groq, mas a conta utilizada não
possuía acesso a ele. A solução foi adaptada para um modelo disponível.

---

## 6. Segurança das credenciais

A chave da API foi mantida no arquivo `.env`.

O repositório contém apenas `.env.example`, sem valores reais.

Durante o desenvolvimento, a chave chegou a ser adicionada por engano a um
commit local.

O GitHub Push Protection detectou o segredo e bloqueou o envio.

A credencial foi removida do commit e o `.gitignore` da raiz foi corrigido
para impedir o versionamento do `.env`.

Essa situação reforçou a importância de tratar credenciais como informação
sensível e manter secrets fora do controle de versão.

---

## 7. Arquitetura do agente

No Nível 2, o agente não recebe toda a base diretamente.

Ele possui ferramentas que consultam informações específicas:

- `historico_cliente`
- `operacoes_do_dia`
- `perfil_canal`
- `operacoes_sinalizadas`

A decisão de quais ferramentas utilizar é realizada pelo próprio modelo.

### Trade-off

Uma implementação mais simples poderia executar todas as ferramentas para
todos os clientes antes de chamar o modelo.

Essa abordagem foi evitada porque isso transformaria o agente em um fluxo
fixo, além de aumentar:

- uso de tokens;
- latência;
- quantidade de dados enviados ao modelo.

O agente foi instruído a consultar apenas as ferramentas necessárias para
cada investigação.

Durante os testes, clientes com diferentes tipos de sinalização utilizaram
sequências diferentes de ferramentas.

---

## 8. Controle de inferências do agente

Uma versão inicial do agente produziu recomendações excessivamente fortes,
como bloqueio de conta e afirmações relacionadas à possibilidade de origem
ilícita dos recursos.

Essas conclusões não eram sustentadas pelos dados disponíveis.

Por isso, o prompt do agente foi alterado para deixar explícito que:

- flags são sinais de triagem;
- ausência de evidência não deve ser preenchida por suposição;
- o modelo não deve afirmar intenção criminosa;
- recomendações devem ser proporcionais;
- a conclusão deve apoiar análise humana.

Essa mudança reduziu inferências não justificadas e tornou os pareceres mais
conservadores.

---

## 9. Execução em lote e limites da API

O agente foi executado sobre os 10 clientes mais priorizados.

Durante a execução foi encontrado um limite de tokens por minuto da API
utilizada.

Para evitar falhas no processamento em lote, foi implementado retry com espera
progressiva.

Também foi adicionada uma pausa entre clientes.

### Trade-off

Essa abordagem aumenta a duração total do processamento, mas evita falhas por
rate limit e permite concluir o lote sem intervenção manual.

Em um ambiente de produção, eu consideraria:

- filas assíncronas;
- controle centralizado de rate limit;
- cache de respostas;
- processamento paralelo respeitando a cota disponível.

---

## 10. Métricas do agente

Na execução dos 10 clientes foram registrados:

- número de chamadas ao LLM;
- tokens de entrada e saída;
- total de tokens;
- latência por cliente;
- latência total.

No lote final foram realizadas 40 chamadas ao LLM, com 61.496 tokens no total.

A média foi de aproximadamente 6.149 tokens por cliente e 21,81 segundos de
latência por cliente.

Essas métricas permitem avaliar o custo operacional do agente e identificar
oportunidades de otimização.

---

## 11. Confronto entre regras e agente

Foi definido um critério determinístico de risco para permitir comparação com
o agente.

O critério utilizado foi:

- baixo: nenhum evento determinístico;
- médio: um evento;
- alto: dois ou mais eventos, ou ocorrência de duas tipologias.

O confronto apresentou:

- 10 clientes comparados;
- 4 concordâncias;
- 6 divergências;
- taxa de concordância de 40%.

As divergências ocorreram nos clientes sinalizados por múltiplas operações de
valor atípico.

Nesses casos, a regra classificou risco alto devido à quantidade de eventos,
enquanto o agente manteve risco médio ao considerar a ausência de outros sinais,
como fracionamento ou concentração temporal.

Essa divergência foi considerada relevante.

O objetivo do agente não é reproduzir mecanicamente as regras, mas utilizar
contexto adicional para complementar a triagem.

Uma taxa de concordância baixa, isoladamente, não significa que o agente está
errado.

As divergências devem ser analisadas individualmente.

---

## 12. Limitações do confronto

O critério determinístico de risco foi criado exclusivamente para permitir a
comparação solicitada no desafio.

Ele não representa uma metodologia real de classificação de risco de PLD.

Em um ambiente real, seria necessário considerar muitos outros fatores, como:

- perfil cadastral;
- atividade econômica;
- histórico temporal mais extenso;
- relacionamentos entre contas;
- dados de beneficiários;
- jurisdição;
- listas restritivas;
- comportamento esperado do cliente.

---

## 13. Escolha do Nível 3

Foi escolhida a:

### Trilha C — Interface Conversacional

A escolha foi feita porque a interface permite aproveitar diretamente os
resultados e pareceres produzidos no Nível 2.

A aplicação foi implementada com Streamlit.

O analista consegue:

- selecionar clientes;
- visualizar risco do agente;
- visualizar risco determinístico;
- consultar a análise estruturada;
- solicitar explicação de um caso;
- gerar um parecer resumido;
- comparar dois clientes;
- fazer perguntas adicionais;
- manter memória da conversa.

Essa interface aproxima a solução de um cenário de uso por um analista humano,
em vez de limitar o resultado a arquivos de saída.

A Trilha C exige uma interface conversacional com memória e suporte a
explicação, comparação e geração de parecer, e foi escolhida por aproveitar
diretamente o trabalho desenvolvido nos níveis anteriores. 

---

## 14. Memória da interface

A memória da conversa foi implementada utilizando o estado de sessão do
Streamlit.

As mensagens anteriores são mantidas durante a sessão e enviadas novamente ao
modelo quando o analista faz uma nova pergunta.

Isso permite perguntas contextuais.

Por exemplo:

1. o analista solicita a explicação de um cliente;
2. depois pergunta apenas "Quais são as limitações dessa conclusão?";
3. a aplicação mantém o contexto e responde sobre o mesmo caso.

### Limitação

A memória existe apenas durante a sessão atual.

Ela não é persistida em banco de dados.

Em uma aplicação real, seria necessário implementar armazenamento persistente,
controle de acesso e políticas de retenção.

---

## 15. Limitações gerais da solução

A solução foi desenvolvida para um conjunto pequeno de dados fictícios.

Ela não contempla:

- autenticação;
- autorização por usuário;
- persistência de sessões;
- banco de dados;
- processamento distribuído;
- monitoramento em tempo real;
- observabilidade completa;
- avaliação automática de qualidade do LLM;
- versionamento de prompts;
- testes de regressão de prompts;
- mecanismos formais de human-in-the-loop;
- integração com sistemas bancários reais.

Além disso, respostas de modelos de linguagem podem variar mesmo com
temperaturas baixas.

---

## 16. O que faria com mais tempo

Com mais tempo, as principais evoluções seriam:

### Cache

Implementaria cache baseado em:

- cliente;
- prompt;
- versão do modelo;
- conjunto de evidências.

Isso reduziria custo, latência e impacto de limites da API.

### Persistência

Utilizaria um banco de dados para armazenar:

- investigações;
- pareceres;
- histórico de conversas;
- decisões do analista;
- métricas de execução.

### Avaliação do LLM

Criaria um conjunto fixo de casos de teste e métricas para comparar:

- diferentes prompts;
- diferentes modelos;
- estabilidade das classificações;
- aderência às evidências.

### Observabilidade

Registraria:

- tokens;
- latência;
- ferramenta selecionada;
- erros;
- retries;
- versão do prompt;
- versão do modelo.

### Segurança

Adicionaria:

- autenticação;
- autorização;
- auditoria;
- gestão centralizada de secrets;
- proteção contra prompt injection;
- sanitização de entradas;
- controles sobre dados sensíveis.

### Arquitetura

Em um cenário maior, separaria o sistema em componentes:

1. pipeline de ingestão e limpeza;
2. motor de regras;
3. serviço de ferramentas;
4. serviço do agente;
5. armazenamento de resultados;
6. interface para analistas.

---

## 17. Conclusão das decisões

A principal escolha arquitetural foi tratar o LLM como uma camada de
interpretação sobre evidências previamente calculadas.

As regras determinísticas mantêm o comportamento objetivo e auditável.

O agente adiciona contexto e flexibilidade.

A interface permite que um analista humano explore os resultados e questione
as conclusões.

A solução não pretende automatizar decisões finais de PLD, mas demonstrar como
regras, ferramentas e modelos de linguagem podem trabalhar juntos para apoiar
uma triagem humana.