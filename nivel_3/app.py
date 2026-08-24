import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from groq import Groq


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Assistente PLD",
    page_icon="🔎",
    layout="wide",
)

PASTA_NIVEL_3 = Path(__file__).resolve().parent
RAIZ_PROJETO = PASTA_NIVEL_3.parent

CAMINHO_OUTPUTS = RAIZ_PROJETO / "outputs"
CAMINHO_LOTE = CAMINHO_OUTPUTS / "lote_clientes.json"
CAMINHO_CONFRONTO = CAMINHO_OUTPUTS / "confronto.csv"

load_dotenv(RAIZ_PROJETO / ".env")

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    st.error(
        "GROQ_API_KEY não encontrada. "
        "Configure a chave no arquivo .env."
    )
    st.stop()

client = Groq(api_key=api_key)


# ============================================================
# CARREGAMENTO DOS RESULTADOS
# ============================================================

@st.cache_data
def carregar_resultados():
    if not CAMINHO_LOTE.exists():
        raise FileNotFoundError(
            "outputs/lote_clientes.json não encontrado."
        )

    with open(
        CAMINHO_LOTE,
        "r",
        encoding="utf-8",
    ) as arquivo:
        lote = json.load(arquivo)

    df_lote = pd.DataFrame(lote)

    if CAMINHO_CONFRONTO.exists():
        df_confronto = pd.read_csv(
            CAMINHO_CONFRONTO
        )
    else:
        df_confronto = pd.DataFrame()

    return df_lote, df_confronto


try:
    df_lote, df_confronto = carregar_resultados()

except Exception as erro:
    st.error(
        f"Erro ao carregar os resultados: {erro}"
    )
    st.stop()


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def obter_cliente(cliente_id):
    linha = df_lote[
        df_lote["cliente_id"] == cliente_id
    ]

    if linha.empty:
        return None

    return linha.iloc[0].to_dict()


def obter_confronto(cliente_id):
    if df_confronto.empty:
        return None

    linha = df_confronto[
        df_confronto["cliente_id"] == cliente_id
    ]

    if linha.empty:
        return None

    return linha.iloc[0].to_dict()


def montar_contexto_cliente(cliente_id):
    cliente = obter_cliente(cliente_id)

    if cliente is None:
        return {
            "erro": "Cliente não encontrado."
        }

    confronto = obter_confronto(
        cliente_id
    )

    contexto = {
        "cliente_id": cliente_id,
        "nivel_risco_agente":
            cliente.get("nivel_risco"),

        "tipologia_suspeita":
            cliente.get("tipologia_suspeita"),

        "principais_evidencias":
            cliente.get("principais_evidencias"),

        "justificativa":
            cliente.get("justificativa"),

        "recomendacao":
            cliente.get("recomendacao"),

        "ferramentas_usadas":
            cliente.get("ferramentas_usadas"),

        "total_tokens":
            cliente.get("total_tokens"),

        "latencia_total_segundos":
            cliente.get(
                "latencia_total_segundos"
            ),
    }

    if confronto is not None:
        contexto["confronto"] = {
            "eventos_fracionamento":
                confronto.get(
                    "eventos_fracionamento"
                ),

            "eventos_valor_atipico":
                confronto.get(
                    "eventos_valor_atipico"
                ),

            "risco_deterministico":
                confronto.get(
                    "risco_deterministico"
                ),

            "risco_agente":
                confronto.get(
                    "risco_agente"
                ),

            "resultado_confronto":
                confronto.get(
                    "resultado_confronto"
                ),
        }

    return contexto


def consultar_llm(pergunta, contexto):
    mensagens = [
        {
            "role": "system",
            "content": """
Você é um assistente de apoio à triagem de PLD.

Responda utilizando exclusivamente as evidências
fornecidas no contexto.

Regras:
- não invente informações;
- não conclua ocorrência de ilícito sem evidência;
- diferencie sinalização determinística de conclusão;
- considere limitações dos dados;
- seja objetivo;
- apoie a análise humana;
- não realize cálculos novos quando os resultados
  já estiverem fornecidos.
"""
        }
    ]

    # Memória da conversa
    for mensagem in st.session_state.mensagens:
        mensagens.append(
            {
                "role": mensagem["role"],
                "content": mensagem["content"],
            }
        )

    mensagens.append(
        {
            "role": "user",
            "content": f"""
CONTEXTO DISPONÍVEL:

{json.dumps(
    contexto,
    ensure_ascii=False,
    indent=2,
    default=str
)}

PERGUNTA DO ANALISTA:

{pergunta}
"""
        }
    )

    resposta = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=mensagens,
        temperature=0.1,
    )

    return (
        resposta
        .choices[0]
        .message
        .content
    )


# ============================================================
# MEMÓRIA DA CONVERSA
# ============================================================

if "mensagens" not in st.session_state:
    st.session_state.mensagens = []


# ============================================================
# INTERFACE
# ============================================================

st.title(
    "🔎 Assistente de Investigação PLD"
)

st.caption(
    "Interface conversacional para análise "
    "dos clientes sinalizados no Nível 2."
)


clientes = sorted(
    df_lote[
        "cliente_id"
    ].dropna().unique()
)


# ============================================================
# BARRA LATERAL
# ============================================================

with st.sidebar:

    st.header(
        "Clientes"
    )

    cliente_principal = st.selectbox(
        "Cliente principal",
        clientes,
    )

    cliente_comparacao = st.selectbox(
        "Comparar com",
        ["Nenhum"] + clientes,
    )

    if st.button(
        "Limpar memória da conversa"
    ):
        st.session_state.mensagens = []
        st.rerun()


# ============================================================
# VISÃO DO CLIENTE
# ============================================================

contexto_principal = montar_contexto_cliente(
    cliente_principal
)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Cliente",
        cliente_principal,
    )

with col2:
    st.metric(
        "Risco do agente",
        contexto_principal.get(
            "nivel_risco_agente",
            "-"
        ),
    )

with col3:
    confronto = contexto_principal.get(
        "confronto",
        {}
    )

    st.metric(
        "Risco determinístico",
        confronto.get(
            "risco_deterministico",
            "-"
        ),
    )


# ============================================================
# DETALHES
# ============================================================

with st.expander(
    "Ver análise estruturada"
):

    st.json(
        contexto_principal,
        expanded=True,
    )


# ============================================================
# COMPARAÇÃO
# ============================================================

contexto_analise = {
    "cliente_principal":
        contexto_principal
}


if (
    cliente_comparacao != "Nenhum"
    and cliente_comparacao
    != cliente_principal
):

    contexto_secundario = (
        montar_contexto_cliente(
            cliente_comparacao
        )
    )

    contexto_analise[
        "cliente_comparacao"
    ] = contexto_secundario

    st.subheader(
        "Comparação"
    )

    comparacao = pd.DataFrame(
        [
            {
                "cliente":
                    cliente_principal,

                "risco_agente":
                    contexto_principal.get(
                        "nivel_risco_agente"
                    ),

                "risco_deterministico":
                    contexto_principal
                    .get(
                        "confronto",
                        {}
                    )
                    .get(
                        "risco_deterministico"
                    ),
            },
            {
                "cliente":
                    cliente_comparacao,

                "risco_agente":
                    contexto_secundario.get(
                        "nivel_risco_agente"
                    ),

                "risco_deterministico":
                    contexto_secundario
                    .get(
                        "confronto",
                        {}
                    )
                    .get(
                        "risco_deterministico"
                    ),
            },
        ]
    )

    st.dataframe(
        comparacao,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# AÇÕES RÁPIDAS
# ============================================================

st.subheader(
    "Ações rápidas"
)

acao1, acao2, acao3 = st.columns(3)


if acao1.button(
    "Explicar o caso"
):
    pergunta_rapida = (
        f"Explique de forma objetiva por que "
        f"o cliente {cliente_principal} "
        f"foi sinalizado."
    )

    st.session_state.mensagens.append(
        {
            "role": "user",
            "content": pergunta_rapida,
        }
    )

    resposta = consultar_llm(
        pergunta_rapida,
        contexto_analise,
    )

    st.session_state.mensagens.append(
        {
            "role": "assistant",
            "content": resposta,
        }
    )

    st.rerun()


if acao2.button(
    "Gerar parecer resumido"
):
    pergunta_rapida = (
        f"Gere um parecer resumido para "
        f"o cliente {cliente_principal}, "
        f"destacando risco, evidências, "
        f"limitações e recomendação."
    )

    st.session_state.mensagens.append(
        {
            "role": "user",
            "content": pergunta_rapida,
        }
    )

    resposta = consultar_llm(
        pergunta_rapida,
        contexto_analise,
    )

    st.session_state.mensagens.append(
        {
            "role": "assistant",
            "content": resposta,
        }
    )

    st.rerun()


if acao3.button(
    "Comparar clientes"
):

    if (
        cliente_comparacao
        == "Nenhum"
        or cliente_comparacao
        == cliente_principal
    ):
        st.warning(
            "Selecione outro cliente "
            "na barra lateral."
        )

    else:
        pergunta_rapida = (
            f"Compare os clientes "
            f"{cliente_principal} e "
            f"{cliente_comparacao}. "
            f"Destaque diferenças de risco, "
            f"evidências e limitações."
        )

        st.session_state.mensagens.append(
            {
                "role": "user",
                "content": pergunta_rapida,
            }
        )

        resposta = consultar_llm(
            pergunta_rapida,
            contexto_analise,
        )

        st.session_state.mensagens.append(
            {
                "role": "assistant",
                "content": resposta,
            }
        )

        st.rerun()


# ============================================================
# HISTÓRICO DO CHAT
# ============================================================

st.subheader(
    "Conversa"
)

for mensagem in st.session_state.mensagens:

    with st.chat_message(
        mensagem["role"]
    ):
        st.markdown(
            mensagem["content"]
        )


# ============================================================
# CHAT
# ============================================================

pergunta = st.chat_input(
    "Pergunte sobre o cliente selecionado..."
)

if pergunta:

    st.session_state.mensagens.append(
        {
            "role": "user",
            "content": pergunta,
        }
    )

    with st.chat_message("user"):
        st.markdown(pergunta)

    with st.chat_message("assistant"):

        with st.spinner(
            "Analisando..."
        ):

            resposta = consultar_llm(
                pergunta,
                contexto_analise,
            )

        st.markdown(
            resposta
        )

    st.session_state.mensagens.append(
        {
            "role": "assistant",
            "content": resposta,
        }
    )