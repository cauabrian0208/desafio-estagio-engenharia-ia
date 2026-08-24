# Desafio Técnico — Engenharia de Inteligência Artificial

Solução desenvolvida para o desafio técnico de estágio em Engenharia de Inteligência Artificial.

O projeto simula um cenário de Prevenção à Lavagem de Dinheiro (PLD), no qual operações financeiras são analisadas utilizando uma combinação de:

- tratamento de dados com Python e pandas;
- regras determinísticas;
- modelos de linguagem;
- agente com ferramentas;
- comparação entre regras e LLM;
- interface conversacional para apoio à análise humana.

Todos os dados utilizados são fictícios e foram fornecidos exclusivamente para o desafio.

---

## Estrutura do projeto

```text
.
├── dados/
├── docs/
│   ├── DECISOES.md
│   └── USO_DE_IA.md
├── nivel_1/
│   └── nivel_1.ipynb
├── nivel_2/
│   ├── agente.py
│   ├── confronto.py
│   ├── nivel_2.ipynb
│   └── tools.py
├── nivel_3/
│   └── app.py
├── outputs/
├── .env.example
├── .gitignore
├── ENTREGA.yaml
├── README.md
└── requirements.txt
```

---

## Tecnologias utilizadas

- Python
- pandas
- Jupyter Notebook
- Groq API
- `openai/gpt-oss-20b`
- Pydantic
- Streamlit
- Git / GitHub

---

## Configuração

### 1. Criar ambiente virtual

No Windows:

```powershell
python -m venv .venv
```

Ative o ambiente:

```powershell
.\.venv\Scripts\Activate.ps1
```

Caso o PowerShell bloqueie a execução:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

Depois:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Instalar dependências

```powershell
python -m pip install -r requirements.txt
```

### 3. Configurar a API

Copie o arquivo:

```text
.env.example
```

para:

```text
.env
```

E configure:

```env
GROQ_API_KEY=sua_chave_aqui
```

A chave real não deve ser adicionada ao Git.

---

## Nível 1 — Dados e primeira análise com LLM

O Nível 1 está em:

```text
nivel_1/nivel_1.ipynb
```

O notebook contém as saídas já executadas.

### Tratamento dos dados

Foram identificados problemas como:

- operações duplicadas;
- datas ausentes;
- valores em BRL e USD.

As duplicidades foram removidas pelo identificador da operação.

Datas ausentes foram preservadas como valores nulos para evitar descarte desnecessário de operações válidas para análises não temporais.

Valores em USD foram convertidos utilizando exclusivamente a taxa de câmbio fornecida no arquivo de dados.

### Regras implementadas

#### Regra 1 — Fracionamento

Sinaliza situações em que um cliente realiza, na mesma data:

- 3 ou mais operações;
- soma superior a R$ 50.000;
- nenhuma operação individual igual ou superior a R$ 20.000.

#### Regra 2 — Valor atípico

Sinaliza operações superiores a cinco vezes a mediana das operações do próprio cliente.

A regra é aplicada apenas para clientes com pelo menos quatro operações.

### Análise com LLM

Um cliente sinalizado foi analisado por um modelo de linguagem.

A resposta foi validada em estrutura contendo:

- nível de risco;
- tipologia suspeita;
- red flags;
- justificativa.

Também foram comparadas duas estratégias de prompt.

O segundo prompt apresentou instruções mais explícitas para limitar a resposta às evidências disponíveis, produzindo uma análise mais objetiva e concisa.

---

## Nível 2 — Escala e agente

O Nível 2 utiliza a base maior:

```text
dados/dados_nivel_2.json
```

As mesmas regras do Nível 1 foram reaplicadas em escala.

Os 10 clientes mais sinalizados foram selecionados considerando:

1. número de sinalizações;
2. volume total como critério de desempate.

### Ferramentas do agente

O agente possui ferramentas para consultar informações sob demanda:

#### `historico_cliente`

Retorna um resumo agregado das operações do cliente.

#### `operacoes_do_dia`

Retorna as operações de um cliente em uma determinada data.

#### `perfil_canal`

Analisa a distribuição das operações por canal.

#### `operacoes_sinalizadas`

Retorna as operações que acionaram alguma regra determinística.

O modelo decide quais ferramentas utilizar de acordo com o caso.

As ferramentas não são executadas automaticamente em todas as investigações.

### Agente de investigação

O agente está implementado em:

```text
nivel_2/agente.py
```

Foi utilizado:

```text
openai/gpt-oss-20b
```

via Groq.

O agente:

1. recebe o identificador do cliente;
2. decide quais ferramentas consultar;
3. analisa as evidências retornadas;
4. produz um parecer estruturado.

O modelo foi instruído a tratar as flags como sinais de triagem, e não como provas de atividade ilícita.

Também foi orientado a evitar inferências não sustentadas pelos dados.

---

## Execução em lote

O agente foi executado sobre os 10 clientes priorizados.

Foram registradas métricas de:

- tokens;
- número de chamadas ao LLM;
- latência;
- ferramentas utilizadas.

### Resultado da execução

| Métrica | Resultado |
|---|---:|
| Clientes processados | 10 |
| Respostas válidas | 10 |
| Chamadas ao LLM | 40 |
| Tokens totais | 61.496 |
| Média de tokens por cliente | 6.149,60 |
| Latência total | 218,10 s |
| Latência média por cliente | 21,81 s |

Durante o lote ocorreram limites temporários de tokens por minuto da API.

Foi implementado retry com espera progressiva para evitar a interrupção do processamento.

Os resultados estão disponíveis em:

```text
outputs/lote_clientes.csv
outputs/lote_clientes.json
outputs/metricas_execucao.csv
```

---

## Confronto entre regras e agente

O confronto está implementado em:

```text
nivel_2/confronto.py
```

Foi criado um critério determinístico de risco para permitir a comparação com a classificação do agente.

Critério adotado:

- **baixo:** nenhum evento determinístico;
- **médio:** um evento;
- **alto:** dois ou mais eventos ou presença das duas tipologias.

### Resultado

| Métrica | Resultado |
|---|---:|
| Clientes comparados | 10 |
| Concordâncias | 4 |
| Divergências | 6 |
| Taxa de concordância | 40% |

As divergências ocorreram principalmente nos casos de múltiplas operações classificadas como valor atípico.

As regras determinísticas elevaram esses casos para risco alto pelo número de eventos.

O agente, por outro lado, manteve alguns casos como risco médio ao não encontrar sinais adicionais como fracionamento ou concentração temporal.

Essa divergência foi considerada útil, pois demonstra que o agente não apenas repete mecanicamente o resultado das regras.

Os resultados estão em:

```text
outputs/confronto.csv
outputs/confronto_resumo.json
```

---

## Nível 3 — Interface Conversacional

Foi escolhida a:

**Trilha C — Interface Conversacional**

A aplicação foi construída com Streamlit e está em:

```text
nivel_3/app.py
```

A interface permite ao analista:

- selecionar um cliente;
- consultar seu nível de risco;
- visualizar a classificação determinística;
- acessar a análise estruturada;
- pedir explicações sobre o caso;
- gerar parecer resumido;
- comparar dois clientes;
- fazer perguntas adicionais;
- manter memória da conversa durante a sessão.

### Executando a interface

Na raiz do projeto:

```powershell
python -m streamlit run nivel_3/app.py
```

O Streamlit disponibilizará a aplicação localmente, normalmente em:

```text
http://localhost:8501
```

---

## Interface

### Tela principal

![Interface principal](outputs/interface_principal.png)

### Memória da conversa

A interface mantém o contexto da conversa durante a sessão.

Por exemplo, depois de solicitar a explicação de um cliente, o analista pode perguntar:

> Quais são as limitações dessa conclusão?

sem repetir todo o contexto.

![Memória da conversa](outputs/interface_memoria.png)

### Comparação entre clientes

Também é possível selecionar dois clientes e solicitar uma comparação de:

- risco;
- evidências;
- tipologia;
- limitações;
- recomendações.

![Comparação de clientes](outputs/interface_comparacao.png)

---

## Decisões técnicas

As principais decisões, trade-offs e limitações estão documentados em:

```text
docs/DECISOES.md
```

Entre os pontos discutidos estão:

- separação entre cálculos e interpretação;
- tratamento de dados ausentes;
- arquitetura do agente;
- seleção dinâmica de ferramentas;
- controle de inferências do LLM;
- rate limits;
- confronto entre regras e agente;
- escolha da interface conversacional;
- limitações e possíveis evoluções.

---

## Uso de Inteligência Artificial

O uso de ferramentas de IA durante o desenvolvimento está descrito em:

```text
docs/USO_DE_IA.md
```

O documento registra:

- onde a IA auxiliou;
- como as sugestões foram validadas;
- problemas encontrados;
- momentos em que sugestões da IA precisaram ser corrigidas.

---

## Limitações

Esta solução foi desenvolvida para dados fictícios e possui caráter experimental.

Ela não representa um sistema real de decisão de PLD.

Entre as principais limitações estão:

- pequena quantidade de dados;
- ausência de informações cadastrais;
- ausência de histórico de longo prazo;
- ausência de informações regulatórias adicionais;
- ausência de autenticação;
- memória conversacional não persistente;
- dependência de uma API externa para o LLM;
- sensibilidade a limites de uso da API.

As classificações devem ser interpretadas como apoio à triagem humana.

---

## Possíveis evoluções

Com mais tempo, eu exploraria:

- cache de respostas do LLM;
- persistência das investigações;
- banco de dados;
- autenticação e autorização;
- observabilidade de custo e latência;
- avaliação automatizada de prompts;
- versionamento de prompts;
- testes automatizados;
- proteção contra prompt injection;
- human-in-the-loop estruturado;
- integração com serviços reais de dados;
- containerização com Docker.

---

## Conclusão

O projeto demonstra uma arquitetura híbrida em que:

```text
Dados
  ↓
Tratamento com pandas
  ↓
Regras determinísticas
  ↓
Priorização de clientes
  ↓
Agente com ferramentas
  ↓
Parecer estruturado
  ↓
Confronto regra x agente
  ↓
Interface para análise humana
```

A principal ideia foi manter cálculos objetivos e auditáveis fora do LLM, utilizando o modelo somente para interpretação das evidências e apoio à decisão humana.