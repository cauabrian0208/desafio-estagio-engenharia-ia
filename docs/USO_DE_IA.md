# Uso de Inteligência Artificial

Durante o desenvolvimento utilizei principalmente o **ChatGPT** como ferramenta
de apoio.

Usei a ferramenta para discutir abordagens, entender erros, revisar código,
estruturar prompts, desenvolver o agente com tool calling, apoiar a interface em
Streamlit e revisar a documentação.

Também utilizei o **Devin** na etapa final como uma segunda opinião para revisar
o repositório. Já conhecia a ferramenta e costumo utilizá-la para estudar e
praticar tarefas relacionadas a engenharia de software com IA.

Neste desafio, usei o Devin principalmente para comparar a implementação com o
documento oficial, revisar a estrutura do repositório, conferir outputs e
métricas e procurar possíveis problemas antes da entrega.

## Um caso em que a IA me levou para o caminho errado

Durante os primeiros testes do agente, algumas respostas fizeram inferências e
recomendações mais fortes do que os dados permitiam, incluindo conclusões sobre
possível origem ilícita dos recursos.

Percebi que as evidências disponíveis não eram suficientes para sustentar esse
tipo de afirmação e revisei o prompt do agente. Passei a deixar explícito que uma
flag é apenas um sinal de triagem, que informações ausentes não devem ser
inventadas e que a decisão final depende de revisão humana.

Na revisão final também houve uma sugestão de que o formato visual usado no
exemplo do `ENTREGA.yaml` seria obrigatório. Voltei ao documento original antes
de fazer a alteração e confirmei que aquilo era apenas uma forma válida de
representar a estrutura YAML.

As sugestões das ferramentas de IA foram usadas como apoio e conferidas por meio
da execução do código, inspeção dos outputs e comparação com os requisitos do
desafio.