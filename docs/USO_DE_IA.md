# Uso de Inteligência Artificial

Este documento descreve como ferramentas de Inteligência Artificial foram
utilizadas durante o desenvolvimento do desafio técnico.

---

## 1. Ferramentas utilizadas

Durante o desenvolvimento, utilizei principalmente o ChatGPT como ferramenta
de apoio.

A IA foi utilizada para:

- discutir possíveis abordagens para os requisitos do desafio;
- auxiliar na estruturação do código;
- explicar erros encontrados durante a implementação;
- sugerir melhorias de organização e arquitetura;
- revisar prompts utilizados nos modelos;
- apoiar a implementação do agente com tool calling;
- auxiliar na criação da interface conversacional;
- revisar documentação e organização da entrega.

A implementação foi executada e validada localmente durante o desenvolvimento.

---

## 2. Uso no Nível 1

No Nível 1, a IA foi utilizada como apoio para estruturar a análise
exploratória e revisar a implementação das regras determinísticas.

Os cálculos de:

- fracionamento;
- valor atípico;
- mediana;
- soma;
- contagem de operações;

foram realizados programaticamente com Python e pandas.

O LLM não foi utilizado como substituto desses cálculos.

Também utilizei IA para discutir a construção e melhoria dos prompts utilizados
para gerar os pareceres.

---

## 3. Uso no Nível 2

No Nível 2, a IA foi utilizada como apoio na implementação da arquitetura do
agente.

Foram discutidos pontos como:

- definição das ferramentas;
- formato das funções;
- tool calling;
- tratamento das respostas do modelo;
- registro das ferramentas utilizadas;
- controle de tokens;
- medição de latência;
- tratamento de rate limit;
- execução em lote;
- confronto entre regras determinísticas e agente.

O comportamento final foi validado executando o agente sobre os dados
fornecidos no desafio.

---

## 4. Uso no Nível 3

Para o Nível 3 foi escolhida a Trilha C — Interface Conversacional.

A IA foi utilizada como apoio na implementação da aplicação em Streamlit.

A interface permite:

- selecionar um cliente;
- consultar sua análise;
- solicitar explicações;
- gerar um parecer resumido;
- comparar dois clientes;
- realizar perguntas adicionais;
- manter contexto durante a conversa.

A aplicação foi executada localmente e as principais funcionalidades foram
testadas manualmente.

---

## 5. Situação em que a IA sugeriu um caminho inadequado

Um dos pontos mais importantes durante o desenvolvimento ocorreu na geração
dos primeiros pareceres do agente.

Em uma versão inicial, o modelo produziu conclusões e recomendações mais fortes
do que as evidências permitiam.

Entre elas estavam recomendações de bloqueio de conta e afirmações que
associavam determinadas movimentações a uma possível origem ilícita.

Os dados disponíveis não eram suficientes para sustentar essas conclusões.

Identifiquei que o problema não estava nos cálculos determinísticos, mas na
liberdade dada ao modelo durante a interpretação.

A solução foi revisar o prompt do agente para estabelecer explicitamente que:

- uma flag representa um sinal de triagem;
- comportamento atípico não comprova atividade ilícita;
- o modelo não deve inventar informações ausentes;
- recomendações devem ser proporcionais às evidências;
- limitações dos dados devem ser mencionadas.

Após a alteração, os pareceres ficaram mais conservadores e aderentes aos dados
disponíveis.

Esse episódio reforçou a necessidade de revisar criticamente respostas
produzidas por modelos de linguagem.

---

## 6. Outro problema identificado durante o desenvolvimento

Durante a configuração do agente, uma sugestão inicial utilizava um modelo que
não estava disponível para a conta/API utilizada.

A execução retornou erro informando que o modelo não existia ou que a conta
não possuía acesso.

Em vez de assumir que o código estava correto, verifiquei o erro retornado pela
API e alterei a configuração para um modelo disponível no ambiente utilizado:

`openai/gpt-oss-20b`

Também ocorreram erros de rate limit durante o processamento dos clientes.

Para evitar que uma limitação temporária da API interrompesse todo o lote, foi
implementado tratamento de erro com novas tentativas e espera entre chamadas.

---

## 7. Validação das sugestões da IA

As sugestões geradas por IA não foram tratadas como automaticamente corretas.

A validação foi realizada por meio de:

- execução local do código;
- inspeção das saídas;
- comparação com os dados originais;
- análise das exceções retornadas;
- conferência das regras determinísticas;
- comparação entre resultados do agente e das regras;
- testes manuais da interface.

Quando uma sugestão não funcionava ou produzia um comportamento inadequado, a
implementação era revisada.

---

## 8. Responsabilidade sobre a solução

A IA foi utilizada como ferramenta de apoio ao desenvolvimento, e não como
substituta da validação da solução.

As decisões finais sobre:

- arquitetura;
- regras utilizadas;
- tratamento dos dados;
- prompts;
- ferramentas disponíveis ao agente;
- critérios de confronto;
- estrutura da interface;
- conteúdo entregue;

foram tomadas considerando os requisitos do desafio e os resultados observados
durante a execução.

Todo código utilizado na entrega foi executado e testado no ambiente local
antes da finalização do projeto.

---

## 9. Considerações finais

O uso de IA acelerou principalmente atividades de implementação, depuração e
documentação.

Ao mesmo tempo, o desenvolvimento mostrou que respostas de IA precisam ser
avaliadas criticamente.

Os principais casos em que isso ficou evidente foram:

1. recomendações excessivamente fortes produzidas pelo agente;
2. utilização inicial de um modelo indisponível;
3. necessidade de adaptar a implementação aos limites reais da API.

Por isso, a IA foi utilizada como ferramenta de assistência, enquanto a
validação final permaneceu baseada na execução do código, nos dados fornecidos
e nos requisitos do desafio.