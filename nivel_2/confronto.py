import json
from pathlib import Path

import pandas as pd


# ============================================================
# CAMINHOS DO PROJETO
# ============================================================

PASTA_NIVEL_2 = Path(__file__).resolve().parent
RAIZ_PROJETO = PASTA_NIVEL_2.parent

CAMINHO_DADOS = (
    RAIZ_PROJETO
    / "dados"
    / "dados_nivel_2.json"
)

CAMINHO_RESULTADOS_AGENTE = (
    RAIZ_PROJETO
    / "outputs"
    / "lote_clientes.csv"
)

CAMINHO_OUTPUTS = (
    RAIZ_PROJETO
    / "outputs"
)


# ============================================================
# CARREGAMENTO E LIMPEZA DOS DADOS
# ============================================================

def carregar_dados():
    """
    Carrega os dados do Nível 2 e aplica os mesmos
    tratamentos utilizados no notebook:

    - remoção de duplicidades;
    - conversão de datas;
    - normalização dos valores para BRL.
    """

    with open(
        CAMINHO_DADOS,
        "r",
        encoding="utf-8"
    ) as arquivo:

        dados = json.load(
            arquivo
        )


    taxa_cambio = dados[
        "taxa_cambio_usd_brl"
    ]


    df = pd.DataFrame(
        dados["operacoes"]
    )


    # Remove duplicidades pelo ID
    df = (
        df
        .drop_duplicates(
            subset=["id"],
            keep="first"
        )
        .copy()
    )


    # Converte a data
    df["data"] = pd.to_datetime(
        df["data"],
        errors="coerce"
    )


    # Normaliza os valores para BRL
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

    - mesmo cliente e mesma data;
    - pelo menos 3 operações;
    - soma superior a R$ 50.000;
    - cada operação individual abaixo de R$ 20.000.

    Para o confronto, um cliente/data sinalizado
    representa UM evento de fracionamento.
    """

    df_com_data = (
        df
        .dropna(
            subset=["data"]
        )
        .copy()
    )


    resumo_dia = (
        df_com_data
        .groupby(
            [
                "cliente_id",
                "data"
            ]
        )
        .agg(
            quantidade_operacoes=(
                "id",
                "count"
            ),
            soma_dia_brl=(
                "valor_brl",
                "sum"
            ),
            maior_operacao_brl=(
                "valor_brl",
                "max"
            ),
        )
        .reset_index()
    )


    casos = resumo_dia[
        (
            resumo_dia[
                "quantidade_operacoes"
            ] >= 3
        )
        &
        (
            resumo_dia[
                "soma_dia_brl"
            ] > 50000
        )
        &
        (
            resumo_dia[
                "maior_operacao_brl"
            ] < 20000
        )
    ].copy()


    return casos


# ============================================================
# REGRA 2 — VALOR ATÍPICO
# ============================================================

def aplicar_regra_valor_atipico(df):
    """
    Regra 2:

    - cliente com pelo menos 4 operações;
    - operação superior a 5 vezes a mediana
      das operações daquele cliente.

    Cada operação sinalizada representa um evento
    de valor atípico para o confronto.
    """

    estatisticas_cliente = (
        df
        .groupby(
            "cliente_id"
        )
        .agg(
            quantidade_operacoes=(
                "id",
                "count"
            ),
            mediana_valor_brl=(
                "valor_brl",
                "median"
            ),
        )
        .reset_index()
    )


    df_regra = df.merge(
        estatisticas_cliente,
        on="cliente_id",
        how="left",
        validate="many_to_one"
    )


    casos = df_regra[
        (
            df_regra[
                "quantidade_operacoes"
            ] >= 4
        )
        &
        (
            df_regra[
                "valor_brl"
            ]
            >
            5
            * df_regra[
                "mediana_valor_brl"
            ]
        )
    ].copy()


    return casos


# ============================================================
# RESUMO DETERMINÍSTICO POR CLIENTE
# ============================================================

def construir_resumo_deterministico(df):
    """
    Constrói um resumo da quantidade de eventos
    identificados por cada regra para cada cliente.
    """

    casos_fracionamento = (
        aplicar_regra_fracionamento(
            df
        )
    )


    casos_valor_atipico = (
        aplicar_regra_valor_atipico(
            df
        )
    )


    # --------------------------------------------------------
    # Fracionamento
    # --------------------------------------------------------
    #
    # Cada cliente/data sinalizado conta como um evento.
    # --------------------------------------------------------

    resumo_fracionamento = (
        casos_fracionamento
        .groupby(
            "cliente_id"
        )
        .size()
        .reset_index(
            name="eventos_fracionamento"
        )
    )


    # --------------------------------------------------------
    # Valor atípico
    # --------------------------------------------------------
    #
    # Cada operação sinalizada conta como um evento.
    # --------------------------------------------------------

    resumo_atipico = (
        casos_valor_atipico
        .groupby(
            "cliente_id"
        )
        .size()
        .reset_index(
            name="eventos_valor_atipico"
        )
    )


    # Todos os clientes da base
    clientes = pd.DataFrame(
        {
            "cliente_id": sorted(
                df[
                    "cliente_id"
                ].unique()
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


    colunas_eventos = [
        "eventos_fracionamento",
        "eventos_valor_atipico",
    ]


    resumo[
        colunas_eventos
    ] = (
        resumo[
            colunas_eventos
        ]
        .fillna(0)
        .astype(int)
    )


    resumo["total_eventos"] = (
        resumo[
            "eventos_fracionamento"
        ]
        +
        resumo[
            "eventos_valor_atipico"
        ]
    )


    return resumo


# ============================================================
# CLASSIFICAÇÃO DE RISCO DETERMINÍSTICA
# ============================================================

def classificar_risco_deterministico(linha):
    """
    Critério adotado exclusivamente para possibilitar
    o confronto entre regras e agente.

    BAIXO:
        nenhuma regra acionada.

    MÉDIO:
        um único evento determinístico.

    ALTO:
        dois ou mais eventos determinísticos
        OU ocorrência das duas tipologias.

    Essa classificação representa priorização de triagem.
    Não representa confirmação de ilícito.
    """

    fracionamento = int(
        linha[
            "eventos_fracionamento"
        ]
    )

    valor_atipico = int(
        linha[
            "eventos_valor_atipico"
        ]
    )

    total = int(
        linha[
            "total_eventos"
        ]
    )


    # Duas tipologias diferentes
    if (
        fracionamento > 0
        and valor_atipico > 0
    ):
        return "alto"


    # Dois ou mais eventos
    if total >= 2:
        return "alto"


    # Um único evento
    if total == 1:
        return "médio"


    return "baixo"


# ============================================================
# NORMALIZAÇÃO DO RISCO PRODUZIDO PELO AGENTE
# ============================================================

def normalizar_risco(valor):
    """
    Padroniza possíveis variações textuais
    na classificação do agente.
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
        "media": "médio",
        "média": "médio",
        "medium": "médio",
        "high": "alto",
        "low": "baixo",
    }


    return substituicoes.get(
        valor,
        valor
    )


# ============================================================
# ANÁLISE DE UMA DIVERGÊNCIA
# ============================================================

def analisar_divergencia(linha):
    """
    Analisa cada divergência do lote final.

    Esta análise representa uma revisão humana dos resultados
    produzidos pelas regras e pelo agente.

    Não existe ground truth de lavagem de dinheiro na base.
    Portanto, a avaliação indica qual classificação parece
    mais proporcional às evidências disponíveis para triagem,
    e não qual abordagem provou estar objetivamente correta.
    """

    cliente_id = linha[
        "cliente_id"
    ]


    # ========================================================
    # AVALIAÇÃO HUMANA DAS DIVERGÊNCIAS DO LOTE
    # ========================================================

    avaliacoes = {

        "CLI-014": {
            "quem_parece_mais_adequado":
                "nenhum dos dois isoladamente",

            "analise_divergencia":
                (
                    "A regra determinística classificou o cliente "
                    "como risco alto porque três operações foram "
                    "identificadas como valores atípicos. Esse critério "
                    "é objetivo, mas pode superestimar o risco ao tratar "
                    "a repetição da mesma regra como evidência suficiente "
                    "para risco alto. Por outro lado, classificar o caso "
                    "como baixo parece permissivo diante da existência "
                    "de três operações que ultrapassaram o limiar de "
                    "atipicidade. Uma classificação intermediária de "
                    "risco médio parece mais proporcional, mantendo o "
                    "caso priorizado para revisão humana sem transformar "
                    "os alertas em comprovação de ilícito."
                )
        },


        "CLI-023": {
            "quem_parece_mais_adequado":
                "nenhum dos dois isoladamente",

            "analise_divergencia":
                (
                    "A regra determinística elevou o caso para risco "
                    "alto pela existência de duas operações de valor "
                    "atípico. O agente reduziu para baixo após considerar "
                    "o histórico, mas as próprias evidências indicam que "
                    "essas operações estão entre as maiores movimentações "
                    "do cliente. Assim, risco alto parece excessivo para "
                    "uma única tipologia simples, enquanto risco baixo "
                    "reduz demais a importância dos alertas. Risco médio "
                    "seria uma priorização mais equilibrada para análise "
                    "humana adicional."
                )
        },


        "CLI-028": {
            "quem_parece_mais_adequado":
                "agente, com revisão humana",

            "analise_divergencia":
                (
                    "A regra determinística classificou o cliente como "
                    "alto porque duas operações acionaram a mesma regra "
                    "de valor atípico. O agente manteve o caso em risco "
                    "médio, reconhecendo a concentração das operações "
                    "de maior valor sem tratar automaticamente dois "
                    "alertas da mesma tipologia como risco alto. Essa "
                    "classificação parece mais proporcional às evidências "
                    "disponíveis, mantendo a necessidade de revisão sem "
                    "concluir ocorrência de ilícito."
                )
        },


        "CLI-013": {
            "quem_parece_mais_adequado":
                "agente na classificação, com ressalva na justificativa",

            "analise_divergencia":
                (
                    "A classificação de risco médio do agente parece "
                    "mais proporcional do que o risco alto produzido "
                    "automaticamente pela repetição da regra de valor "
                    "atípico. Entretanto, a justificativa do agente fez "
                    "uma inferência excessiva ao sugerir possível intenção "
                    "de ocultar a origem dos recursos. Os dados permitem "
                    "afirmar que houve concentração de operações atípicas, "
                    "mas não permitem inferir intenção criminosa. Portanto, "
                    "a classificação do agente parece razoável, porém sua "
                    "justificativa deveria ser mais conservadora."
                )
        },


        "CLI-005": {
            "quem_parece_mais_adequado":
                "nenhum dos dois isoladamente",

            "analise_divergencia":
                (
                    "A regra determinística atribuiu risco alto pela "
                    "existência de duas operações de valor atípico, mas "
                    "não considera outras características do histórico. "
                    "O agente, por outro lado, reduziu o caso para risco "
                    "baixo. Mesmo sem outros sinais corroborantes, duas "
                    "operações que acionaram a regra ainda justificam "
                    "priorização. Assim, risco médio parece uma posição "
                    "mais proporcional entre o excesso de sensibilidade "
                    "da regra e a classificação mais permissiva do agente."
                )
        },


        "CLI-026": {
            "quem_parece_mais_adequado":
                "agente, com revisão humana",

            "analise_divergencia":
                (
                    "A regra determinística classificou o cliente como "
                    "alto apenas porque duas operações acionaram a mesma "
                    "regra de valor atípico. O agente reconheceu essas "
                    "operações, mas não identificou evidências suficientes "
                    "para elevar automaticamente o caso ao nível máximo "
                    "de priorização. O risco médio parece mais proporcional "
                    "às informações disponíveis e preserva a necessidade "
                    "de acompanhamento humano."
                )
        },
    }


    # ========================================================
    # RETORNO DA AVALIAÇÃO ESPECÍFICA
    # ========================================================

    if cliente_id in avaliacoes:

        avaliacao = avaliacoes[
            cliente_id
        ]

        return pd.Series(
            avaliacao
        )


    # ========================================================
    # FALLBACK PARA OUTRAS DIVERGÊNCIAS
    # ========================================================

    return pd.Series(
        {
            "quem_parece_mais_adequado":
                "depende de revisão humana",

            "analise_divergencia":
                (
                    "As abordagens utilizam critérios diferentes "
                    "e os dados disponíveis não permitem determinar "
                    "objetivamente qual classificação é correta. "
                    "A divergência deve ser analisada a partir das "
                    "evidências específicas do cliente e da "
                    "justificativa produzida pelo agente."
                )
        }
    )

# ============================================================
# EXECUÇÃO DO CONFRONTO
# ============================================================

def executar_confronto():
    """
    Executa o confronto completo entre:

    - classificação determinística;
    - classificação do agente.

    Também calcula concordância e analisa
    individualmente as divergências.
    """

    print("=" * 70)

    print(
        "CONFRONTO — REGRAS DETERMINÍSTICAS x AGENTE"
    )

    print("=" * 70)


    # ========================================================
    # CARREGA OS DADOS
    # ========================================================

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


    # ========================================================
    # CARREGA OS RESULTADOS DO AGENTE
    # ========================================================

    if not CAMINHO_RESULTADOS_AGENTE.exists():

        raise FileNotFoundError(
            "Arquivo outputs/lote_clientes.csv "
            "não encontrado."
        )


    resultados_agente = pd.read_csv(
        CAMINHO_RESULTADOS_AGENTE
    )


    # ========================================================
    # VALIDAÇÃO DO ARQUIVO DO AGENTE
    # ========================================================

    colunas_obrigatorias = [
        "cliente_id",
        "nivel_risco",
        "tipologia_suspeita",
        "justificativa",
        "ferramentas_usadas",
        "total_tokens",
        "latencia_total_segundos",
    ]


    colunas_ausentes = [
        coluna
        for coluna in colunas_obrigatorias
        if coluna
        not in resultados_agente.columns
    ]


    if colunas_ausentes:

        raise ValueError(
            "Colunas necessárias não encontradas em "
            "outputs/lote_clientes.csv: "
            + ", ".join(
                colunas_ausentes
            )
        )


    # ========================================================
    # NORMALIZA O RISCO DO AGENTE
    # ========================================================

    resultados_agente[
        "risco_agente"
    ] = resultados_agente[
        "nivel_risco"
    ].apply(
        normalizar_risco
    )


    # ========================================================
    # COLUNAS UTILIZADAS NO CONFRONTO
    # ========================================================

    colunas_agente = [
        "cliente_id",
        "risco_agente",
        "tipologia_suspeita",
        "justificativa",
        "ferramentas_usadas",
        "total_tokens",
        "latencia_total_segundos",
    ]


    # Custo é opcional aqui.
    #
    # Se a coluna existir, ela será preservada.
    # Se não existir, o confronto continua normalmente.
    if (
        "custo_total_estimado_usd"
        in resultados_agente.columns
    ):

        colunas_agente.append(
            "custo_total_estimado_usd"
        )


    # ========================================================
    # JUNÇÃO
    # ========================================================

    confronto = (
        resultados_agente[
            colunas_agente
        ]
        .merge(
            resumo_deterministico,
            on="cliente_id",
            how="left",
            validate="one_to_one"
        )
    )


    # ========================================================
    # CONCORDÂNCIA
    # ========================================================

    confronto[
        "concordancia"
    ] = (
        confronto[
            "risco_agente"
        ]
        ==
        confronto[
            "risco_deterministico"
        ]
    )


    confronto[
        "resultado_confronto"
    ] = confronto[
        "concordancia"
    ].map(
        {
            True: "concordante",
            False: "divergente",
        }
    )


    # ========================================================
    # CAMPOS DE ANÁLISE
    # ========================================================

    confronto[
        "quem_parece_mais_adequado"
    ] = "-"

    confronto[
        "analise_divergencia"
    ] = "-"


    mascara_divergencia = (
        ~confronto[
            "concordancia"
        ]
    )


    # ========================================================
    # ANALISA SOMENTE AS DIVERGÊNCIAS
    # ========================================================

    if mascara_divergencia.any():

        analises = (
            confronto.loc[
                mascara_divergencia
            ]
            .apply(
                analisar_divergencia,
                axis=1
            )
        )


        confronto.loc[
            mascara_divergencia,
            [
                "quem_parece_mais_adequado",
                "analise_divergencia",
            ]
        ] = analises.values


    # ========================================================
    # MÉTRICAS DE CONCORDÂNCIA
    # ========================================================

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


    # ========================================================
    # RESULTADO POR CLIENTE
    # ========================================================

    colunas_exibicao = [
        "cliente_id",
        "eventos_fracionamento",
        "eventos_valor_atipico",
        "total_eventos",
        "risco_deterministico",
        "risco_agente",
        "resultado_confronto",
    ]


    print(
        "\nRESULTADO POR CLIENTE:\n"
    )


    print(
        confronto[
            colunas_exibicao
        ].to_string(
            index=False
        )
    )


    # ========================================================
    # RESUMO
    # ========================================================

    print(
        "\n"
        + "=" * 70
    )

    print(
        "RESUMO"
    )

    print(
        "=" * 70
    )


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


    # ========================================================
    # DIVERGÊNCIAS
    # ========================================================

    divergencias = confronto[
        ~confronto[
            "concordancia"
        ]
    ].copy()


    print(
        "\n"
        + "=" * 70
    )

    print(
        "ANÁLISE DAS DIVERGÊNCIAS"
    )

    print(
        "=" * 70
    )


    if divergencias.empty:

        print(
            "Nenhuma divergência encontrada."
        )


    else:

        for _, linha in (
            divergencias.iterrows()
        ):

            print(
                "\n"
                + "-" * 70
            )


            print(
                f"Cliente: "
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
                "\nQuem parece mais adequado:"
            )


            print(
                linha[
                    "quem_parece_mais_adequado"
                ]
            )


            print(
                "\nAnálise da divergência:"
            )


            print(
                linha[
                    "analise_divergencia"
                ]
            )


            print(
                "\nJustificativa produzida pelo agente:"
            )


            print(
                linha[
                    "justificativa"
                ]
            )


        print(
            "\n"
            + "-" * 70
        )


    # ========================================================
    # SALVAMENTO DOS OUTPUTS
    # ========================================================

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


    # ========================================================
    # RESUMO EM JSON
    # ========================================================

    avaliacao_divergencias = (
        divergencias[
            [
                "cliente_id",
                "risco_deterministico",
                "risco_agente",
                "eventos_fracionamento",
                "eventos_valor_atipico",
                "quem_parece_mais_adequado",
                "analise_divergencia",
            ]
        ]
        .to_dict(
            orient="records"
        )
    )


    resumo_json = {
        "clientes_comparados": (
            quantidade_clientes
        ),

        "concordancias": (
            quantidade_concordantes
        ),

        "divergencias": (
            quantidade_divergentes
        ),

        "taxa_concordancia_percentual": round(
            taxa_concordancia,
            2
        ),

        "criterio_deterministico": {
            "baixo": (
                "nenhum evento determinístico"
            ),

            "medio": (
                "um único evento determinístico"
            ),

            "alto": (
                "dois ou mais eventos determinísticos "
                "ou ocorrência das duas tipologias"
            ),
        },

        "observacao": (
            "A classificação determinística representa "
            "priorização de triagem e não confirmação "
            "de ocorrência de ilícito."
        ),

        "clientes_divergentes": (
            divergencias[
                "cliente_id"
            ].tolist()
        ),

        "avaliacao_divergencias": (
            avaliacao_divergencias
        ),
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


    # ========================================================
    # CONFIRMAÇÃO DOS ARQUIVOS
    # ========================================================

    print(
        "\n"
        + "=" * 70
    )

    print(
        "ARQUIVOS GERADOS"
    )

    print(
        "=" * 70
    )


    print(
        "confronto.csv:",
        caminho_csv.exists()
    )


    print(
        "confronto_resumo.json:",
        caminho_json.exists()
    )


    return (
        confronto,
        resumo_json
    )


# ============================================================
# EXECUÇÃO DIRETA
# ============================================================

if __name__ == "__main__":

    executar_confronto()