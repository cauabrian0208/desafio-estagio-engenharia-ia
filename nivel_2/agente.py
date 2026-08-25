import os
import json
import time
from pathlib import Path

from groq import Groq, RateLimitError
from dotenv import load_dotenv


# ============================================================
# IMPORTAÇÃO DAS FERRAMENTAS
# ============================================================

# Permite funcionar tanto:
# python nivel_2/agente.py
#
# quanto:
# import agente
# dentro do notebook em nivel_2/

try:
    from .tools import (
        historico_cliente,
        operacoes_do_dia,
        perfil_canal,
        operacoes_sinalizadas,
    )
except ImportError:
    from tools import (
        historico_cliente,
        operacoes_do_dia,
        perfil_canal,
        operacoes_sinalizadas,
    )


# ============================================================
# CAMINHOS DO PROJETO
# ============================================================

PASTA_NIVEL_2 = Path(__file__).resolve().parent
RAIZ_PROJETO = PASTA_NIVEL_2.parent

CAMINHO_ENV = RAIZ_PROJETO / ".env"


# ============================================================
# CONFIGURAÇÃO DA API
# ============================================================

load_dotenv(
    dotenv_path=CAMINHO_ENV,
    override=True
)

api_key = os.getenv(
    "GROQ_API_KEY",
    ""
).strip()

if not api_key:
    raise ValueError(
        "GROQ_API_KEY não encontrada no arquivo .env"
    )

client = Groq(
    api_key=api_key
)


# ============================================================
# CONFIGURAÇÃO DO MODELO
# ============================================================

MODELO = "openai/gpt-oss-20b"


# ============================================================
# PREÇOS UTILIZADOS PARA ESTIMATIVA
# ============================================================
#
# Valores por 1 milhão de tokens.
#
# A estimativa é teórica e utiliza a tarifa pública
# do modelo. Mesmo que a conta esteja em um plano gratuito,
# o valor é calculado para fins de observabilidade.
#
# Entrada: US$ 0.075 / 1M tokens
# Saída:   US$ 0.30  / 1M tokens
# ============================================================

PRECO_ENTRADA_POR_MILHAO = 0.075
PRECO_SAIDA_POR_MILHAO = 0.30


def calcular_custo_estimado(
    tokens_entrada,
    tokens_saida
):
    """
    Calcula o custo teórico da chamada em dólares.
    """

    custo_entrada = (
        tokens_entrada
        / 1_000_000
        * PRECO_ENTRADA_POR_MILHAO
    )

    custo_saida = (
        tokens_saida
        / 1_000_000
        * PRECO_SAIDA_POR_MILHAO
    )

    return custo_entrada + custo_saida


# ============================================================
# DEFINIÇÃO DAS FERRAMENTAS PARA O LLM
# ============================================================

FERRAMENTAS = [
    {
        "type": "function",
        "function": {
            "name": "historico_cliente",
            "description": (
                "Retorna um resumo agregado do histórico financeiro "
                "do cliente. Use quando precisar comparar o caso "
                "sinalizado com o comportamento geral."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cliente_id": {
                        "type": "string",
                        "description": (
                            "Identificador do cliente."
                        )
                    }
                },
                "required": [
                    "cliente_id"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "operacoes_do_dia",
            "description": (
                "Retorna as operações de um cliente em uma data "
                "específica. Use quando houver concentração ou "
                "possível fracionamento em um mesmo dia."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cliente_id": {
                        "type": "string",
                        "description": (
                            "Identificador do cliente."
                        )
                    },
                    "data": {
                        "type": "string",
                        "description": (
                            "Data no formato YYYY-MM-DD."
                        )
                    }
                },
                "required": [
                    "cliente_id",
                    "data"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "perfil_canal",
            "description": (
                "Retorna a distribuição de uso de canais do cliente. "
                "Use somente quando o padrão de canais for relevante "
                "para a investigação."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cliente_id": {
                        "type": "string",
                        "description": (
                            "Identificador do cliente."
                        )
                    }
                },
                "required": [
                    "cliente_id"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "operacoes_sinalizadas",
            "description": (
                "Retorna as operações do cliente que acionaram "
                "regras determinísticas. É uma boa ferramenta "
                "inicial para entender por que o cliente foi "
                "priorizado."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cliente_id": {
                        "type": "string",
                        "description": (
                            "Identificador do cliente."
                        )
                    }
                },
                "required": [
                    "cliente_id"
                ]
            }
        }
    }
]


# ============================================================
# EXECUÇÃO DAS FERRAMENTAS
# ============================================================

def executar_ferramenta(
    nome,
    argumentos,
    df
):
    """
    Faz a ligação entre o tool call do modelo
    e a função Python correspondente.
    """

    cliente_id = argumentos[
        "cliente_id"
    ]

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
        "erro": (
            f"Ferramenta desconhecida: {nome}"
        )
    }


# ============================================================
# CHAMADA AO MODELO COM RETRY
# ============================================================

def chamar_modelo_com_retry(
    mensagens
):
    """
    Consulta o modelo e faz retry em caso
    de RateLimitError.
    """

    max_tentativas = 5

    for tentativa in range(
        1,
        max_tentativas + 1
    ):
        try:

            inicio = time.perf_counter()

            resposta = (
                client
                .chat
                .completions
                .create(
                    model=MODELO,
                    messages=mensagens,
                    tools=FERRAMENTAS,
                    tool_choice="auto",
                    temperature=0
                )
            )

            latencia = (
                time.perf_counter()
                - inicio
            )

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

            time.sleep(
                espera
            )


# ============================================================
# VALIDAÇÃO DO PARECER FINAL
# ============================================================

def validar_parecer_final(
    conteudo,
    cliente_id
):
    """
    Verifica se a resposta final possui
    a estrutura esperada.

    Retorna:
    - valido
    - parecer estruturado
    - erro
    """

    try:

        dados = json.loads(
            conteudo
        )

    except (
        json.JSONDecodeError,
        TypeError
    ) as erro:

        return {
            "valido": False,
            "parecer": None,
            "erro": str(erro)
        }


    if not isinstance(
        dados,
        dict
    ):
        return {
            "valido": False,
            "parecer": None,
            "erro": (
                "A resposta final não é "
                "um objeto JSON."
            )
        }


    campos_obrigatorios = [
        "cliente_id",
        "nivel_risco",
        "tipologia_suspeita",
        "principais_evidencias",
        "justificativa",
        "recomendacao",
    ]


    campos_ausentes = [
        campo
        for campo in campos_obrigatorios
        if campo not in dados
    ]


    if campos_ausentes:
        return {
            "valido": False,
            "parecer": None,
            "erro": (
                "Campos ausentes: "
                + ", ".join(
                    campos_ausentes
                )
            )
        }


    risco = str(
        dados["nivel_risco"]
    ).strip().lower()


    substituicoes = {
        "medio": "médio",
        "media": "médio",
        "média": "médio",
        "high": "alto",
        "medium": "médio",
        "low": "baixo",
    }


    risco = substituicoes.get(
        risco,
        risco
    )


    if risco not in {
        "baixo",
        "médio",
        "alto"
    }:
        return {
            "valido": False,
            "parecer": None,
            "erro": (
                "nivel_risco inválido: "
                f"{dados['nivel_risco']}"
            )
        }


    if not isinstance(
        dados["principais_evidencias"],
        list
    ):
        return {
            "valido": False,
            "parecer": None,
            "erro": (
                "principais_evidencias "
                "deve ser uma lista."
            )
        }


    # O cliente investigado é definido pelo código,
    # e não pelo modelo.
    dados["cliente_id"] = cliente_id
    dados["nivel_risco"] = risco


    return {
        "valido": True,
        "parecer": dados,
        "erro": None
    }


# ============================================================
# AGENTE
# ============================================================

def investigar_cliente(
    df,
    cliente_id
):
    """
    Investiga um cliente utilizando seleção
    dinâmica de ferramentas.

    O modelo decide quais ferramentas consultar
    conforme as evidências encontradas.
    """

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

- Não faça soma, média, mediana, contagem, percentual ou comparação numérica por conta própria.
- Utilize somente os cálculos retornados pelas ferramentas.
- Se um cálculo necessário não estiver disponível, não o estime.

- Não afirme que NÃO existe concentração temporal, padrão de canais,
  recorrência ou qualquer outro comportamento que dependa de uma
  ferramenta que você não consultou.
- Se não consultou a ferramenta necessária para verificar determinado
  aspecto, diga apenas que esse aspecto não foi avaliado.

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
                "Ele foi priorizado previamente por regras "
                "determinísticas de PLD. "
                "Use somente as ferramentas necessárias e "
                "produza o parecer final."
            )
        }
    ]


    ferramentas_usadas = []

    chamadas_llm = []

    ultimo_erro_validacao = None


    # ========================================================
    # LOOP DO AGENTE
    # ========================================================

    for iteracao in range(
        1,
        7
    ):

        resposta, latencia = (
            chamar_modelo_com_retry(
                mensagens
            )
        )


        uso = resposta.usage


        tokens_entrada = (
            uso.prompt_tokens or 0
        )

        tokens_saida = (
            uso.completion_tokens or 0
        )

        tokens_total = (
            uso.total_tokens or 0
        )


        custo_estimado = (
            calcular_custo_estimado(
                tokens_entrada,
                tokens_saida
            )
        )


        chamadas_llm.append(
            {
                "numero_chamada": len(
                    chamadas_llm
                ) + 1,
                "modelo": MODELO,
                "latencia_segundos": (
                    latencia
                ),
                "tokens_entrada": (
                    tokens_entrada
                ),
                "tokens_saida": (
                    tokens_saida
                ),
                "tokens_total": (
                    tokens_total
                ),
                "custo_estimado_usd": (
                    custo_estimado
                ),
            }
        )


        mensagem = (
            resposta
            .choices[0]
            .message
        )


        mensagens.append(
            mensagem
        )


        # ====================================================
        # RESPOSTA FINAL
        # ====================================================

        if not mensagem.tool_calls:

            validacao = (
                validar_parecer_final(
                    mensagem.content,
                    cliente_id
                )
            )


            if validacao[
                "valido"
            ]:

                parecer = validacao[
                    "parecer"
                ]


                return {
                    "cliente_id": cliente_id,

                    # Mantido para compatibilidade
                    # com códigos anteriores
                    "parecer": json.dumps(
                        parecer,
                        ensure_ascii=False
                    ),

                    # Nova versão estruturada
                    "parecer_estruturado": (
                        parecer
                    ),

                    "resposta_valida": True,

                    "erro_validacao": None,

                    "ferramentas_usadas": (
                        ferramentas_usadas
                    ),

                    "chamadas_llm": (
                        chamadas_llm
                    ),

                    "total_tokens": sum(
                        chamada[
                            "tokens_total"
                        ]
                        for chamada
                        in chamadas_llm
                    ),

                    "latencia_total_segundos": sum(
                        chamada[
                            "latencia_segundos"
                        ]
                        for chamada
                        in chamadas_llm
                    ),

                    "custo_total_estimado_usd": sum(
                        chamada[
                            "custo_estimado_usd"
                        ]
                        for chamada
                        in chamadas_llm
                    ),
                }


            # =================================================
            # FORMATO INVÁLIDO
            # =================================================

            ultimo_erro_validacao = (
                validacao["erro"]
            )


            if iteracao < 6:

                mensagens.append(
                    {
                        "role": "user",
                        "content": f"""
Sua resposta final não respeitou a estrutura solicitada.

Erro encontrado:
{ultimo_erro_validacao}

Corrija SOMENTE o formato da resposta.

Retorne apenas um objeto JSON válido com exatamente:

{{
  "cliente_id": "{cliente_id}",
  "nivel_risco": "baixo | médio | alto",
  "tipologia_suspeita": "...",
  "principais_evidencias": ["..."],
  "justificativa": "...",
  "recomendacao": "..."
}}

Não adicione Markdown.
Não adicione texto antes ou depois do JSON.
"""
                    }
                )

                continue


        # ====================================================
        # TOOL CALLS
        # ====================================================

        for chamada in (
            mensagem.tool_calls or []
        ):

            nome = (
                chamada
                .function
                .name
            )


            try:

                argumentos = json.loads(
                    chamada
                    .function
                    .arguments
                )

            except json.JSONDecodeError:

                argumentos = {}


            # O ID correto é controlado
            # pelo código e não pelo LLM.
            argumentos[
                "cliente_id"
            ] = cliente_id


            try:

                resultado = executar_ferramenta(
                    nome,
                    argumentos,
                    df
                )

            except Exception as erro:

                resultado = {
                    "erro": (
                        f"Falha ao executar "
                        f"{nome}: {erro}"
                    )
                }


            ferramentas_usadas.append(
                nome
            )


            mensagens.append(
                {
                    "role": "tool",
                    "tool_call_id": (
                        chamada.id
                    ),
                    "content": json.dumps(
                        resultado,
                        ensure_ascii=False,
                        default=str
                    )
                }
            )


    # ========================================================
    # FALLBACK
    # ========================================================

    parecer_fallback = {
        "cliente_id": cliente_id,
        "nivel_risco": "médio",
        "tipologia_suspeita": (
            "análise inconclusiva"
        ),
        "principais_evidencias": [],
        "justificativa": (
            "O agente atingiu o limite máximo "
            "de iterações antes de concluir a "
            "investigação."
        ),
        "recomendacao": (
            "Realizar análise humana adicional."
        )
    }


    return {
        "cliente_id": cliente_id,

        "parecer": json.dumps(
            parecer_fallback,
            ensure_ascii=False
        ),

        "parecer_estruturado": (
            parecer_fallback
        ),

        "resposta_valida": False,

        "erro_validacao": (
            ultimo_erro_validacao
            or
            "Limite máximo de iterações atingido."
        ),

        "ferramentas_usadas": (
            ferramentas_usadas
        ),

        "chamadas_llm": (
            chamadas_llm
        ),

        "total_tokens": sum(
            chamada["tokens_total"]
            for chamada in chamadas_llm
        ),

        "latencia_total_segundos": sum(
            chamada[
                "latencia_segundos"
            ]
            for chamada in chamadas_llm
        ),

        "custo_total_estimado_usd": sum(
            chamada[
                "custo_estimado_usd"
            ]
            for chamada in chamadas_llm
        ),
    }