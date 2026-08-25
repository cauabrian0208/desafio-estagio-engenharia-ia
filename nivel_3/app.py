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

load_dotenv(
    dotenv_path=RAIZ_PROJETO / ".env",
    override=True,
)

api_key = (os.getenv("GROQ_API_KEY") or "").strip()

if not api_key:
    st.error(
        "GROQ_API_KEY não encontrada. "
        "Configure a chave no arquivo .env."
    )
    st.stop()

client = Groq(api_key=api_key)
MODELO = "openai/gpt-oss-20b"


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

    colunas_lote_obrigatorias = [
        "cliente_id",
        "nivel_risco",
        "tipologia_suspeita",
        "principais_evidencias",
        "justificativa",
        "recomendacao",
    ]

    colunas_ausentes = [
        coluna
        for coluna in colunas_lote_obrigatorias
        if coluna not in df_lote.columns
    ]

    if colunas_ausentes:
        raise ValueError(
            "Colunas obrigatórias ausentes em "
            "outputs/lote_clientes.json: "
            + ", ".join(colunas_ausentes)
        )

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

def limpar_valores(valor):
    """
    Converte NaN/NaT em None e percorre estruturas
    aninhadas para produzir um contexto seguro para JSON.
    """

    if isinstance(valor, dict):
        return {
            chave: limpar_valores(conteudo)
            for chave, conteudo in valor.items()
        }

    if isinstance(valor, list):
        return [
            limpar_valores(item)
            for item in valor
        ]

    if isinstance(valor, tuple):
        return [
            limpar_valores(item)
            for item in valor
        ]

    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass

    return valor


def obter_cliente(cliente_id):
    linha = df_lote[
        df_lote["cliente_id"] == cliente_id
    ]

    if linha.empty:
        return None

    return limpar_valores(
        linha.iloc[0].to_dict()
    )


def obter_confronto(cliente_id):
    if df_confronto.empty:
        return None

    if "cliente_id" not in df_confronto.columns:
        return None

    linha = df_confronto[
        df_confronto["cliente_id"] == cliente_id
    ]

    if linha.empty:
        return None

    return limpar_valores(
        linha.iloc[0].to_dict()
    )


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
        "nivel_risco_agente": cliente.get(
            "nivel_risco"
        ),
        "tipologia_suspeita": cliente.get(
            "tipologia_suspeita"
        ),
        "principais_evidencias": cliente.get(
            "principais_evidencias"
        ),
        "justificativa": cliente.get(
            "justificativa"
        ),
        "recomendacao": cliente.get(
            "recomendacao"
        ),
        "ferramentas_usadas": cliente.get(
            "ferramentas_usadas"
        ),
        "total_tokens": cliente.get(
            "total_tokens"
        ),
        "latencia_total_segundos": cliente.get(
            "latencia_total_segundos"
        ),
    }

    if confronto is not None:
        contexto["confronto"] = {
            "eventos_fracionamento": confronto.get(
                "eventos_fracionamento"
            ),
            "eventos_valor_atipico": confronto.get(
                "eventos_valor_atipico"
            ),
            "risco_deterministico": confronto.get(
                "risco_deterministico"
            ),
            "risco_agente": confronto.get(
                "risco_agente"
            ),
            "resultado_confronto": confronto.get(
                "resultado_confronto"
            ),
            "quem_parece_mais_adequado": confronto.get(
                "quem_parece_mais_adequado"
            ),
            "analise_divergencia": confronto.get(
                "analise_divergencia"
            ),
        }

    return limpar_valores(contexto)


def criar_chave_conversa(
    cliente_principal,
    cliente_comparacao,
):
    """
    Mantém memórias separadas para cada contexto de análise.

    Exemplo:
    - CLI-029
    - CLI-029__vs__CLI-014
    """

    if (
        cliente_comparacao != "Nenhum"
        and cliente_comparacao != cliente_principal
    ):
        return (
            f"{cliente_principal}"
            f"__vs__"
            f"{cliente_comparacao}"
        )

    return str(cliente_principal)


def descricao_conversa(
    cliente_principal,
    cliente_comparacao,
):
    if (
        cliente_comparacao != "Nenhum"
        and cliente_comparacao != cliente_principal
    ):
        return (
            f"{cliente_principal} × "
            f"{cliente_comparacao}"
        )

    return str(cliente_principal)


def consultar_llm(
    pergunta,
    contexto,
    historico,
):
    """
    Consulta o modelo usando:

    1. instruções de segurança/escopo;
    2. contexto estruturado atual;
    3. histórico anterior da conversa;
    4. pergunta atual uma única vez.
    """

    mensagens = [
        {
            "role": "system",
            "content": """
Você é um assistente de apoio à triagem de PLD.

Use exclusivamente as informações fornecidas no contexto
estruturado e no histórico desta conversa.

Regras:
- não invente informações;
- não conclua ocorrência de ilícito sem evidência;
- não atribua intenção criminosa ao cliente;
- diferencie sinalização determinística de conclusão;
- considere as limitações dos dados;
- seja objetivo e apoie a análise humana;
- não realize cálculos novos quando os resultados já
  estiverem fornecidos;
- se uma informação não estiver no contexto, diga que ela
  não foi informada ou não pôde ser avaliada;
- não transforme a justificativa anterior do agente em fato:
  trate-a como uma análise prévia que pode ter limitações;
- não afirme ausência de um padrão quando o contexto não
  trouxer evidência suficiente para essa conclusão.
""",
        },
        {
            "role": "system",
            "content": (
                "CONTEXTO ESTRUTURADO ATUAL:\n\n"
                + json.dumps(
                    contexto,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            ),
        },
    ]

    # Inclui somente mensagens ANTERIORES.
    # A pergunta atual ainda não foi adicionada ao histórico.
    for mensagem in historico:
        role = mensagem.get("role")
        content = mensagem.get("content")

        if (
            role in {"user", "assistant"}
            and isinstance(content, str)
        ):
            mensagens.append(
                {
                    "role": role,
                    "content": content,
                }
            )

    # A pergunta atual entra exatamente uma vez.
    mensagens.append(
        {
            "role": "user",
            "content": pergunta,
        }
    )

    resposta = client.chat.completions.create(
        model=MODELO,
        messages=mensagens,
        temperature=0.1,
    )

    conteudo = (
        resposta
        .choices[0]
        .message
        .content
    )

    if not conteudo:
        raise RuntimeError(
            "O modelo retornou uma resposta vazia."
        )

    return conteudo.strip()


def registrar_interacao(
    pergunta,
    contexto,
    chave_conversa,
):
    """
    Executa a pergunta e só registra a nova interação
    depois que a chamada ao LLM termina com sucesso.

    Isso evita enviar a pergunta atual duas vezes.
    """

    historico = st.session_state.conversas.setdefault(
        chave_conversa,
        [],
    )

    resposta = consultar_llm(
        pergunta=pergunta,
        contexto=contexto,
        historico=historico,
    )

    historico.append(
        {
            "role": "user",
            "content": pergunta,
        }
    )

    historico.append(
        {
            "role": "assistant",
            "content": resposta,
        }
    )

    return resposta


# ============================================================
# MEMÓRIA DA CONVERSA
# ============================================================

if "conversas" not in st.session_state:
    st.session_state.conversas = {}


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
    ].dropna().astype(str).unique()
)

if not clientes:
    st.error(
        "Nenhum cliente foi encontrado nos resultados do lote."
    )
    st.stop()


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

    chave_conversa_atual = criar_chave_conversa(
        cliente_principal,
        cliente_comparacao,
    )

    descricao_atual = descricao_conversa(
        cliente_principal,
        cliente_comparacao,
    )

    st.caption(
        "A memória é separada por cliente "
        "e por comparação."
    )

    if st.button(
        "Limpar memória desta conversa"
    ):
        st.session_state.conversas[
            chave_conversa_atual
        ] = []
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
            "-",
        ) or "-",
    )

with col3:
    confronto = contexto_principal.get(
        "confronto",
        {},
    ) or {}

    st.metric(
        "Risco determinístico",
        confronto.get(
            "risco_deterministico",
            "-",
        ) or "-",
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
    "cliente_principal": contexto_principal
}

if (
    cliente_comparacao != "Nenhum"
    and cliente_comparacao != cliente_principal
):
    contexto_secundario = montar_contexto_cliente(
        cliente_comparacao
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
                "cliente": cliente_principal,
                "risco_agente": contexto_principal.get(
                    "nivel_risco_agente"
                ),
                "risco_deterministico": (
                    contexto_principal
                    .get("confronto", {})
                    .get("risco_deterministico")
                ),
            },
            {
                "cliente": cliente_comparacao,
                "risco_agente": contexto_secundario.get(
                    "nivel_risco_agente"
                ),
                "risco_deterministico": (
                    contexto_secundario
                    .get("confronto", {})
                    .get("risco_deterministico")
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
        f"foi sinalizado. Diferencie os alertas "
        f"determinísticos da avaliação do agente."
    )

    try:
        registrar_interacao(
            pergunta=pergunta_rapida,
            contexto=contexto_analise,
            chave_conversa=chave_conversa_atual,
        )
        st.rerun()

    except Exception as erro:
        st.error(
            f"Erro ao consultar o modelo: {erro}"
        )


if acao2.button(
    "Gerar parecer resumido"
):
    pergunta_rapida = (
        f"Gere um parecer resumido para "
        f"o cliente {cliente_principal}, "
        f"destacando risco, evidências, "
        f"limitações e recomendação. "
        f"Não trate sinalizações como prova de ilícito."
    )

    try:
        registrar_interacao(
            pergunta=pergunta_rapida,
            contexto=contexto_analise,
            chave_conversa=chave_conversa_atual,
        )
        st.rerun()

    except Exception as erro:
        st.error(
            f"Erro ao consultar o modelo: {erro}"
        )


if acao3.button(
    "Comparar clientes"
):
    if (
        cliente_comparacao == "Nenhum"
        or cliente_comparacao == cliente_principal
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
            f"evidências, divergências entre regra "
            f"e agente e limitações."
        )

        try:
            registrar_interacao(
                pergunta=pergunta_rapida,
                contexto=contexto_analise,
                chave_conversa=chave_conversa_atual,
            )
            st.rerun()

        except Exception as erro:
            st.error(
                f"Erro ao consultar o modelo: {erro}"
            )


# ============================================================
# HISTÓRICO DO CHAT
# ============================================================

st.subheader(
    "Conversa"
)

st.caption(
    f"Memória atual: {descricao_atual}"
)

mensagens_atuais = st.session_state.conversas.setdefault(
    chave_conversa_atual,
    [],
)

if not mensagens_atuais:
    st.info(
        "Ainda não há mensagens nesta conversa. "
        "Use uma ação rápida ou escreva uma pergunta abaixo."
    )

for mensagem in mensagens_atuais:
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
    with st.chat_message("user"):
        st.markdown(pergunta)

    with st.chat_message("assistant"):
        with st.spinner(
            "Analisando..."
        ):
            try:
                resposta = registrar_interacao(
                    pergunta=pergunta,
                    contexto=contexto_analise,
                    chave_conversa=chave_conversa_atual,
                )

            except Exception as erro:
                resposta = None
                st.error(
                    f"Erro ao consultar o modelo: {erro}"
                )

        if resposta:
            st.markdown(
                resposta
            )
