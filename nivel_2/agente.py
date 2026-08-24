import os
import json
import time

from groq import Groq, RateLimitError
from dotenv import load_dotenv

from tools import (
    historico_cliente,
    operacoes_do_dia,
    perfil_canal,
    operacoes_sinalizadas,
)


load_dotenv("../.env")

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY não encontrada no arquivo .env")

client = Groq(api_key=api_key)


FERRAMENTAS = [
    {
        "type": "function",
        "function": {
            "name": "historico_cliente",
            "description": (
                "Retorna um resumo agregado do histórico financeiro do cliente. "
                "Use quando precisar comparar o caso sinalizado com o comportamento geral."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cliente_id": {
                        "type": "string",
                        "description": "Identificador do cliente."
                    }
                },
                "required": ["cliente_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "operacoes_do_dia",
            "description": (
                "Retorna as operações de um cliente em uma data específica. "
                "Use quando houver concentração ou possível fracionamento em um mesmo dia."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cliente_id": {
                        "type": "string",
                        "description": "Identificador do cliente."
                    },
                    "data": {
                        "type": "string",
                        "description": "Data no formato YYYY-MM-DD."
                    }
                },
                "required": ["cliente_id", "data"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "perfil_canal",
            "description": (
                "Retorna a distribuição de uso de canais do cliente. "
                "Use somente quando o padrão de canais for relevante para a investigação."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cliente_id": {
                        "type": "string",
                        "description": "Identificador do cliente."
                    }
                },
                "required": ["cliente_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "operacoes_sinalizadas",
            "description": (
                "Retorna as operações do cliente que acionaram regras determinísticas. "
                "É uma boa ferramenta inicial para entender por que o cliente foi priorizado."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cliente_id": {
                        "type": "string",
                        "description": "Identificador do cliente."
                    }
                },
                "required": ["cliente_id"]
            }
        }
    }
]


def executar_ferramenta(nome, argumentos, df):
    cliente_id = argumentos["cliente_id"]

    if nome == "historico_cliente":
        return historico_cliente(
            df,
            cliente_id
        )

    if nome == "operacoes_do_dia":
        return operacoes_do_dia(
            df,
            cliente_id,
            argumentos["data"]
        )

    if nome == "perfil_canal":
        return perfil_canal(
            df,
            cliente_id
        )

    if nome == "operacoes_sinalizadas":
        return operacoes_sinalizadas(
            df,
            cliente_id
        )

    return {
        "erro": f"Ferramenta desconhecida: {nome}"
    }


def chamar_modelo_com_retry(mensagens):
    max_tentativas = 5

    for tentativa in range(1, max_tentativas + 1):
        try:
            inicio = time.perf_counter()

            resposta = client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=mensagens,
                tools=FERRAMENTAS,
                tool_choice="auto",
                temperature=0
            )

            latencia = time.perf_counter() - inicio

            return resposta, latencia

        except RateLimitError:
            if tentativa == max_tentativas:
                raise

            espera = 3 * tentativa

            print(
                f"Rate limit atingido. "
                f"Aguardando {espera}s antes da tentativa "
                f"{tentativa + 1}/{max_tentativas}..."
            )

            time.sleep(espera)


def investigar_cliente(df, cliente_id):
    mensagens = [
        {
            "role": "system",
            "content": """
Você é um agente de apoio à triagem de Prevenção à Lavagem de Dinheiro (PLD).

Sua função é investigar um cliente previamente sinalizado por regras determinísticas.

Você possui quatro ferramentas disponíveis:

1. operacoes_sinalizadas
2. historico_cliente
3. operacoes_do_dia
4. perfil_canal

REGRAS PARA USO DAS FERRAMENTAS:

- Escolha apenas as ferramentas necessárias para compreender o caso.
- Não chame todas as ferramentas automaticamente.
- Comece preferencialmente por operacoes_sinalizadas.
- Se houver concentração de operações em uma data específica, considere usar operacoes_do_dia.
- Use historico_cliente quando precisar comparar o comportamento sinalizado com o histórico geral.
- Use perfil_canal apenas quando a distribuição de canais acrescentar evidência relevante.
- Pare de chamar ferramentas quando já houver evidência suficiente para produzir o parecer.

REGRAS DE INTERPRETAÇÃO:

- As flags determinísticas são sinais de triagem, não provas de lavagem de dinheiro.
- Não conclua que existe lavagem de dinheiro, fraude, origem ilícita ou intenção criminosa sem evidência suficiente.
- Não invente fatos.
- Não invente contexto sobre clientes ou contrapartes.
- Não transforme uma regra determinística em conclusão automática de ilícito.
- Não chame média de mediana nem mediana de média.
- Use exatamente os nomes e significados retornados pelas ferramentas.
- Quando os dados forem insuficientes, declare explicitamente essa limitação.
- Seu papel é apoiar a análise humana.

Evite recomendações excessivas como:
- bloqueio automático de conta;
- denúncia automática;
- investigação criminal;
- conclusão definitiva de ilícito.

Prefira recomendações proporcionais, como:
- monitoramento;
- solicitação de documentação;
- análise humana adicional;
- aprofundamento da investigação quando necessário.

AO FINAL, responda SOMENTE em JSON válido com exatamente estes campos:

{
  "cliente_id": "...",
  "nivel_risco": "baixo | médio | alto",
  "tipologia_suspeita": "...",
  "principais_evidencias": [
    "...",
    "..."
  ],
  "justificativa": "...",
  "recomendacao": "..."
}
"""
        },
        {
            "role": "user",
            "content": (
                f"Investigue o cliente {cliente_id}. "
                "Ele foi priorizado previamente por regras determinísticas de PLD. "
                "Use as ferramentas necessárias e produza o parecer final."
            )
        }
    ]

    ferramentas_usadas = []
    chamadas_llm = []

    for _ in range(6):
        resposta, latencia = chamar_modelo_com_retry(
            mensagens
        )

        uso = resposta.usage

        chamadas_llm.append(
            {
                "latencia_segundos": latencia,
                "tokens_entrada": uso.prompt_tokens,
                "tokens_saida": uso.completion_tokens,
                "tokens_total": uso.total_tokens,
            }
        )

        mensagem = resposta.choices[0].message
        mensagens.append(mensagem)

        if not mensagem.tool_calls:
            return {
                "cliente_id": cliente_id,
                "parecer": mensagem.content,
                "ferramentas_usadas": ferramentas_usadas,
                "chamadas_llm": chamadas_llm,
                "total_tokens": sum(
                    chamada["tokens_total"]
                    for chamada in chamadas_llm
                ),
                "latencia_total_segundos": sum(
                    chamada["latencia_segundos"]
                    for chamada in chamadas_llm
                ),
            }

        for chamada in mensagem.tool_calls:
            nome = chamada.function.name

            try:
                argumentos = json.loads(
                    chamada.function.arguments
                )
            except json.JSONDecodeError:
                argumentos = {}

            if "cliente_id" not in argumentos:
                argumentos["cliente_id"] = cliente_id

            resultado = executar_ferramenta(
                nome,
                argumentos,
                df
            )

            ferramentas_usadas.append(nome)

            mensagens.append(
                {
                    "role": "tool",
                    "tool_call_id": chamada.id,
                    "content": json.dumps(
                        resultado,
                        ensure_ascii=False,
                        default=str
                    )
                }
            )

    return {
        "cliente_id": cliente_id,
        "parecer": json.dumps(
            {
                "cliente_id": cliente_id,
                "nivel_risco": "médio",
                "tipologia_suspeita": "análise inconclusiva",
                "principais_evidencias": [],
                "justificativa": (
                    "O agente atingiu o limite máximo de iterações "
                    "antes de concluir a investigação."
                ),
                "recomendacao": (
                    "Realizar análise humana adicional."
                )
            },
            ensure_ascii=False
        ),
        "ferramentas_usadas": ferramentas_usadas,
        "chamadas_llm": chamadas_llm,
        "total_tokens": sum(
            chamada["tokens_total"]
            for chamada in chamadas_llm
        ),
        "latencia_total_segundos": sum(
            chamada["latencia_segundos"]
            for chamada in chamadas_llm
        ),
    }