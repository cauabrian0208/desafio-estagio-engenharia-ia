# Uso de Inteligência Artificial

Durante o desenvolvimento do desafio utilizei principalmente o **ChatGPT**
como ferramenta de apoio.

A IA foi utilizada para:

- discutir possíveis abordagens para os requisitos;
- auxiliar na estruturação e revisão do código;
- explicar erros encontrados durante a implementação;
- revisar os prompts utilizados com o LLM;
- apoiar a implementação do agente com tool calling;
- auxiliar na interface Streamlit;
- revisar a documentação e a organização final do projeto.

As sugestões não foram consideradas automaticamente corretas. O código foi
executado localmente e os resultados foram conferidos com os dados e requisitos
do desafio.

## Um caminho inadequado sugerido pela IA

Durante os primeiros testes do agente, algumas respostas apresentaram
conclusões e recomendações mais fortes do que as evidências disponíveis
permitiam, incluindo sugestões de ações sobre contas e inferências sobre uma
possível origem ilícita dos recursos.

Os dados do desafio não eram suficientes para sustentar essas conclusões.

A partir desse problema, revisei o prompt do agente para deixar explícito que:

- as flags representam sinais de triagem;
- comportamento atípico não comprova atividade ilícita;
- informações ausentes não devem ser inventadas;
- recomendações devem ser proporcionais às evidências;
- a decisão final depende de revisão humana.

Outro ajuste necessário ocorreu quando uma sugestão inicial utilizava um modelo
que não estava disponível na conta utilizada. O erro retornado pela API foi
verificado e a implementação foi adaptada para o modelo disponível:

`openai/gpt-oss-20b`

Também foi necessário adaptar o processamento aos limites reais da API,
implementando retry para situações de rate limit.

## Validação

As sugestões de IA foram validadas por meio de:

- execução local do código;
- inspeção das saídas;
- conferência das regras determinísticas;
- comparação entre regras e agente;
- testes manuais da interface.

A IA foi usada como ferramenta de assistência ao desenvolvimento. A validação
final permaneceu baseada no funcionamento do código, nos dados fornecidos e nos
requisitos do desafio.