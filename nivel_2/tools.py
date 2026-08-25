import pandas as pd


def historico_cliente(df, cliente_id):
    """
    Retorna um resumo agregado do histórico do cliente.
    """
    operacoes = df[df["cliente_id"] == cliente_id].copy()

    if operacoes.empty:
        return {"erro": "Cliente não encontrado"}

    return {
        "cliente_id": cliente_id,
        "quantidade_operacoes": int(len(operacoes)),
        "volume_total_brl": float(operacoes["valor_brl"].sum()),
        "mediana_valor_brl": float(operacoes["valor_brl"].median()),
        "maior_operacao_brl": float(operacoes["valor_brl"].max()),
        "operacoes_fracionamento": int(
            operacoes["flag_fracionamento"].sum()
        ),
        "operacoes_valor_atipico": int(
            operacoes["flag_valor_atipico"].sum()
        ),
    }


def operacoes_do_dia(df, cliente_id, data):
    """
    Retorna as operações do cliente em uma data específica.
    """
    data = pd.to_datetime(data)

    operacoes = df[
        (df["cliente_id"] == cliente_id)
        & (df["data"] == data)
    ].copy()

    if operacoes.empty:
        return []

    return operacoes[
        [
            "id",
            "data",
            "valor_brl",
            "canal",
            "tipo",
            "contraparte",
            "flag_fracionamento",
            "flag_valor_atipico",
        ]
    ].to_dict(orient="records")


def perfil_canal(df, cliente_id):
    """
    Retorna a distribuição do uso de canais pelo cliente.
    """
    operacoes = df[df["cliente_id"] == cliente_id].copy()

    if operacoes.empty:
        return {"erro": "Cliente não encontrado"}

    perfil = (
        operacoes
        .groupby("canal")
        .agg(
            quantidade_operacoes=("id", "count"),
            volume_total_brl=("valor_brl", "sum"),
        )
        .reset_index()
    )

    total = len(operacoes)

    perfil["percentual_operacoes"] = (
        perfil["quantidade_operacoes"] / total * 100
    )

    return perfil.to_dict(orient="records")


# Ferramenta adicional
def operacoes_sinalizadas(df, cliente_id):
    """
    Retorna operações que acionaram alguma regra.
    """
    operacoes = df[
        (df["cliente_id"] == cliente_id)
        & (
            df["flag_fracionamento"]
            | df["flag_valor_atipico"]
        )
    ].copy()

    return operacoes[
        [
            "id",
            "data",
            "valor_brl",
            "canal",
            "tipo",
            "contraparte",
            "flag_fracionamento",
            "flag_valor_atipico",
        ]
    ].to_dict(orient="records")