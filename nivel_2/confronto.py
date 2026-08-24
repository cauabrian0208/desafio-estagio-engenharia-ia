import json
from pathlib import Path

import pandas as pd


# ============================================================
# CAMINHOS DO PROJETO
# ============================================================

PASTA_NIVEL_2 = Path(__file__).resolve().parent
RAIZ_PROJETO = PASTA_NIVEL_2.parent

CAMINHO_DADOS = RAIZ_PROJETO / "dados" / "dados_nivel_2.json"
CAMINHO_RESULTADOS_AGENTE = RAIZ_PROJETO / "outputs" / "lote_clientes.csv"
CAMINHO_OUTPUTS = RAIZ_PROJETO / "outputs"


# ============================================================
# CARREGAMENTO E LIMPEZA DOS DADOS
# ============================================================

def carregar_dados():
    """
    Carrega os dados do Nível 2 e aplica os mesmos tratamentos
    utilizados anteriormente:
    - remoção de duplicidades;
    - conversão de datas;
    - normalização dos valores para BRL.
    """

    with open(
        CAMINHO_DADOS,
        "r",
        encoding="utf-8"
    ) as arquivo:
        dados = json.load(arquivo)

    taxa_cambio = dados["taxa_cambio_usd_brl"]

    df = pd.DataFrame(
        dados["operacoes"]
    )

    # Remove duplicidades pelo identificador da operação
    df = (
        df
        .drop_duplicates(
            subset=["id"],
            keep="first"
        )
        .copy()
    )

    # Converte data
    df["data"] = pd.to_datetime(
        df["data"],
        errors="coerce"
    )

    # Normaliza valores para BRL
    df["valor_brl"] = df.apply(
        lambda linha: (
            linha["valor"] * taxa_cambio
            if linha["moeda"] == "USD"
            else linha["valor"]
        ),
        axis=1
    )

    return df


# ============================================================
# REGRA 1 — FRACIONAMENTO
# ============================================================

def aplicar_regra_fracionamento(df):
    """
    Regra 1:
    - 3 ou mais operações na mesma data;
    - soma superior a R$ 50.000;
    - nenhuma operação individual >= R$ 20.000.

    Retorna os EVENTOS de fracionamento por cliente/data.
    """

    df_com_data = (
        df
        .dropna(subset=["data"])
        .copy()
    )

    resumo_dia = (
        df_com_data
        .groupby(
            ["cliente_id", "data"]
        )
        .agg(
            quantidade_operacoes=("id", "count"),
            soma_dia_brl=("valor_brl", "sum"),
            maior_operacao_brl=("valor_brl", "max"),
        )
        .reset_index()
    )

    casos = resumo_dia[
        (
            resumo_dia["quantidade_operacoes"] >= 3
        )
        & (
            resumo_dia["soma_dia_brl"] > 50000
        )
        & (
            resumo_dia["maior_operacao_brl"] < 20000
        )
    ].copy()

    return casos


# ============================================================
# REGRA 2 — VALOR ATÍPICO
# ============================================================

def aplicar_regra_valor_atipico(df):
    """
    Regra 2:
    operação superior a 5 vezes a mediana do cliente,
    considerando apenas clientes com 4 ou mais operações.

    Retorna as operações que acionaram a regra.
    """

    estatisticas = (
        df
        .groupby("cliente_id")
        .agg(
            quantidade_operacoes=("id", "count"),
            mediana_valor_brl=("valor_brl", "median"),
        )
        .reset_index()
    )

    df_regra = df.merge(
        estatisticas,
        on="cliente_id",
        how="left"
    )

    casos = df_regra[
        (
            df_regra["quantidade_operacoes"] >= 4
        )
        & (
            df_regra["valor_brl"]
            > 5 * df_regra["mediana_valor_brl"]
        )
    ].copy()

    return casos


# ============================================================
# RESUMO DETERMINÍSTICO POR CLIENTE
# ============================================================

def construir_resumo_deterministico(df):
    """
    Constrói um resumo por cliente com a quantidade de eventos
    identificados por cada regra.
    """

    casos_fracionamento = aplicar_regra_fracionamento(
        df
    )

    casos_valor_atipico = aplicar_regra_valor_atipico(
        df
    )

    # Um evento de fracionamento corresponde a um cliente/data
    resumo_fracionamento = (
        casos_fracionamento
        .groupby("cliente_id")
        .size()
        .reset_index(
            name="eventos_fracionamento"
        )
    )

    # Cada operação que ultrapassa o limite da regra 2
    # conta como um evento de valor atípico
    resumo_atipico = (
        casos_valor_atipico
        .groupby("cliente_id")
        .size()
        .reset_index(
            name="eventos_valor_atipico"
        )
    )

    clientes = pd.DataFrame(
        {
            "cliente_id": sorted(
                df["cliente_id"].unique()
            )
        }
    )

    resumo = clientes.merge(
        resumo_fracionamento,
        on="cliente_id",
        how="left"
    )

    resumo = resumo.merge(
        resumo_atipico,
        on="cliente_id",
        how="left"
    )

    resumo[
        [
            "eventos_fracionamento",
            "eventos_valor_atipico"
        ]
    ] = resumo[
        [
            "eventos_fracionamento",
            "eventos_valor_atipico"
        ]
    ].fillna(0).astype(int)

    resumo["total_eventos"] = (
        resumo["eventos_fracionamento"]
        + resumo["eventos_valor_atipico"]
    )

    return resumo


# ============================================================
# CRITÉRIO DETERMINÍSTICO DE RISCO
# ============================================================

def classificar_risco_deterministico(linha):
    """
    Critério adotado para o confronto.

    BAIXO:
        nenhuma regra acionada.

    MÉDIO:
        apenas um evento determinístico identificado.

    ALTO:
        - mais de um evento determinístico; ou
        - ocorrência das duas tipologias de regra.

    O objetivo não é afirmar ocorrência de ilícito.
    A classificação representa somente uma priorização
    determinística para fins de comparação com o agente.
    """

    fracionamento = linha[
        "eventos_fracionamento"
    ]

    valor_atipico = linha[
        "eventos_valor_atipico"
    ]

    total = linha[
        "total_eventos"
    ]

    # Duas tipologias diferentes
    if (
        fracionamento > 0
        and valor_atipico > 0
    ):
        return "alto"

    # Mais de um evento da mesma regra
    if total >= 2:
        return "alto"

    # Um único evento
    if total == 1:
        return "médio"

    return "baixo"


# ============================================================
# NORMALIZAÇÃO DA CLASSIFICAÇÃO DO AGENTE
# ============================================================

def normalizar_risco(valor):
    """
    Padroniza a classificação textual do agente.
    """

    if pd.isna(valor):
        return None

    valor = (
        str(valor)
        .strip()
        .lower()
    )

    substituicoes = {
        "medio": "médio",
        "média": "médio",
        "media": "médio",
        "high": "alto",
        "medium": "médio",
        "low": "baixo",
    }

    return substituicoes.get(
        valor,
        valor
    )


# ============================================================
# CONFRONTO
# ============================================================

def executar_confronto():
    """
    Executa a comparação entre:
    - classificação determinística;
    - classificação produzida pelo agente.
    """

    print("=" * 70)
    print("CONFRONTO — REGRAS DETERMINÍSTICAS x AGENTE")
    print("=" * 70)

    # --------------------------------------------------------
    # Dados determinísticos
    # --------------------------------------------------------

    df = carregar_dados()

    resumo_deterministico = (
        construir_resumo_deterministico(
            df
        )
    )

    resumo_deterministico[
        "risco_deterministico"
    ] = resumo_deterministico.apply(
        classificar_risco_deterministico,
        axis=1
    )

    # --------------------------------------------------------
    # Resultados do agente
    # --------------------------------------------------------

    if not CAMINHO_RESULTADOS_AGENTE.exists():
        raise FileNotFoundError(
            "Arquivo outputs/lote_clientes.csv "
            "não encontrado."
        )

    resultados_agente = pd.read_csv(
        CAMINHO_RESULTADOS_AGENTE
    )

    resultados_agente[
        "risco_agente"
    ] = resultados_agente[
        "nivel_risco"
    ].apply(
        normalizar_risco
    )

    # --------------------------------------------------------
    # Mantém somente os clientes processados pelo agente
    # --------------------------------------------------------

    confronto = resultados_agente[
        [
            "cliente_id",
            "risco_agente",
            "tipologia_suspeita",
            "justificativa",
            "ferramentas_usadas",
            "total_tokens",
            "latencia_total_segundos",
        ]
    ].merge(
        resumo_deterministico,
        on="cliente_id",
        how="left"
    )

    # --------------------------------------------------------
    # Concordância
    # --------------------------------------------------------

    confronto["concordancia"] = (
        confronto["risco_agente"]
        == confronto["risco_deterministico"]
    )

    confronto["resultado_confronto"] = confronto[
        "concordancia"
    ].map(
        {
            True: "concordante",
            False: "divergente",
        }
    )

    # --------------------------------------------------------
    # Resumo
    # --------------------------------------------------------

    quantidade_clientes = len(
        confronto
    )

    quantidade_concordantes = int(
        confronto[
            "concordancia"
        ].sum()
    )

    quantidade_divergentes = (
        quantidade_clientes
        - quantidade_concordantes
    )

    taxa_concordancia = (
        quantidade_concordantes
        / quantidade_clientes
        * 100
        if quantidade_clientes > 0
        else 0
    )

    # --------------------------------------------------------
    # Exibição
    # --------------------------------------------------------

    colunas_exibicao = [
        "cliente_id",
        "eventos_fracionamento",
        "eventos_valor_atipico",
        "total_eventos",
        "risco_deterministico",
        "risco_agente",
        "resultado_confronto",
    ]

    print("\nRESULTADO POR CLIENTE:\n")

    print(
        confronto[
            colunas_exibicao
        ].to_string(
            index=False
        )
    )

    print("\n" + "=" * 70)
    print("RESUMO")
    print("=" * 70)

    print(
        f"Clientes comparados: "
        f"{quantidade_clientes}"
    )

    print(
        f"Concordâncias: "
        f"{quantidade_concordantes}"
    )

    print(
        f"Divergências: "
        f"{quantidade_divergentes}"
    )

    print(
        f"Taxa de concordância: "
        f"{taxa_concordancia:.2f}%"
    )

    # --------------------------------------------------------
    # Divergências
    # --------------------------------------------------------

    divergencias = confronto[
        ~confronto["concordancia"]
    ].copy()

    print("\n" + "=" * 70)
    print("DIVERGÊNCIAS")
    print("=" * 70)

    if divergencias.empty:
        print(
            "Nenhuma divergência encontrada."
        )

    else:
        for _, linha in divergencias.iterrows():

            print(
                f"\nCliente: "
                f"{linha['cliente_id']}"
            )

            print(
                f"Risco determinístico: "
                f"{linha['risco_deterministico']}"
            )

            print(
                f"Risco do agente: "
                f"{linha['risco_agente']}"
            )

            print(
                f"Eventos de fracionamento: "
                f"{linha['eventos_fracionamento']}"
            )

            print(
                f"Eventos de valor atípico: "
                f"{linha['eventos_valor_atipico']}"
            )

            print(
                "Justificativa do agente:"
            )

            print(
                linha["justificativa"]
            )

            print("-" * 70)

    # --------------------------------------------------------
    # Salvamento
    # --------------------------------------------------------

    CAMINHO_OUTPUTS.mkdir(
        parents=True,
        exist_ok=True
    )

    caminho_csv = (
        CAMINHO_OUTPUTS
        / "confronto.csv"
    )

    confronto.to_csv(
        caminho_csv,
        index=False,
        encoding="utf-8-sig"
    )

    resumo_json = {
        "clientes_comparados":
            quantidade_clientes,

        "concordancias":
            quantidade_concordantes,

        "divergencias":
            quantidade_divergentes,

        "taxa_concordancia_percentual":
            round(
                taxa_concordancia,
                2
            ),

        "criterio_deterministico": {
            "baixo":
                "nenhum evento determinístico",

            "medio":
                "um único evento determinístico",

            "alto":
                (
                    "mais de um evento determinístico "
                    "ou ocorrência das duas tipologias"
                )
        },

        "clientes_divergentes":
            divergencias[
                "cliente_id"
            ].tolist()
    }

    caminho_json = (
        CAMINHO_OUTPUTS
        / "confronto_resumo.json"
    )

    with open(
        caminho_json,
        "w",
        encoding="utf-8"
    ) as arquivo:

        json.dump(
            resumo_json,
            arquivo,
            ensure_ascii=False,
            indent=2
        )

    print("\n" + "=" * 70)
    print("ARQUIVOS GERADOS")
    print("=" * 70)

    print(
        f"confronto.csv: "
        f"{caminho_csv.exists()}"
    )

    print(
        f"confronto_resumo.json: "
        f"{caminho_json.exists()}"
    )

    return confronto, resumo_json


# ============================================================
# EXECUÇÃO DIRETA
# ============================================================

if __name__ == "__main__":
    executar_confronto()