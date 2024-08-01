from warnings import simplefilter
import pandas as pd
import numpy as np

pd.options.mode.chained_assignment = None
simplefilter(action="ignore", category=pd.errors.PerformanceWarning)


def retorna_candidatos_federacao(bu, vagas):
    votos_validos = bu["Votos"].sum()
    qe = round(votos_validos/vagas)

    bu["Federação"] = bu["Partido"]

    # Corrige as federações existentes
    federacoes = {
        "PT": "PT/PC do B/PV", "PC do B": "PT/PC do B/PV", "PV": "PT/PC do B/PV",
        "PSDB": "PSDB/CIDADANIA", "CIDADANIA": "PSDB/CIDADANIA", "PPS": "PSDB/CIDADANIA",
        "PSOL": "PSOL/REDE", "REDE": "PSOL/REDE"
    }

    bu.loc[bu["Federação"].isin(federacoes.keys()), "Federação"] = bu.loc[bu["Federação"].isin(
        federacoes.keys()), "Federação"].map(federacoes)

    candidatos = bu[bu["Candidato"] != bu["Partido"]]

    # Regra dos 10% e dos 20% do QE
    candidatos["Maior que 10% QE"] = candidatos["Votos"
                                                ].apply(lambda x: x >= round(qe*0.1))
    candidatos["Maior que 20% QE"] = candidatos["Votos"
                                                ].apply(lambda x: x >= round(qe*0.2))

    # Pega apenas os candidatos com mais de 10%
    candidatos_restantes = candidatos[candidatos["Maior que 10% QE"]]

    # Cria as federações
    federacao = bu[["Federação", "Votos"]].groupby([
        "Federação"]).sum().sort_values("Votos", ascending=False).reset_index()

    # Quociente partidário
    # federacao["qp_normal"] = (federacao["Votos"]/qe)
    federacao["QP"] = np.floor(federacao["Votos"]/qe).astype(int)
    federacao["Vagas"] = federacao["QP"]

    # Regra dos 80% do QE
    federacao["Maior que 80% QE"] = federacao["Votos"].apply(
        lambda x: x >= round(qe*0.8))

    return candidatos_restantes, federacao


def regra_1_qp(agremiacao_com_qp, candidatos_restantes, log):
    # Regra artigo 108 - Candidatos acima de 10% do QE, dentro da quantidade de QP inicial

    eleitos = pd.DataFrame(
        columns=["Candidato", "Partido", "Federação", "Votos", "Regra", "Rodada"])

    regra = "QP"

    for index, linha in agremiacao_com_qp.iterrows():
        lista = candidatos_restantes[candidatos_restantes["Federação"]
                                     == linha["Federação"]].head(linha["QP"])
        aux = pd.DataFrame(
            lista[candidatos_restantes.columns]).reset_index(drop=True)

        candidatos_restantes.drop(index=lista.index, inplace=True)

        aux["Regra"] = regra
        aux["Rodada"] = aux.index + 1

        eleitos = pd.concat([eleitos, aux])

        for i, item in aux.iterrows():
            log.write(
                f'''Regra 1 - QP: Candidato eleito {aux.at[i, "Candidato"]} da \
federação {aux.at[i, "Federação"]} \n''')

    return eleitos.reset_index(drop=True), candidatos_restantes


def regra_sobras(eleitos, vagas, federacao, candidatos_restantes, log, e_80_20=True):
    # Regra artigo 109 incisos I e II - Candidatos acima de 20% do QE,
    # dentro da distrubuição das sobras
    regra = "Sobras 1" if e_80_20 else "Sobras 2"
    regra_str = "Regra 2 - 80-20" if e_80_20 else "Regra 3 - Sobras"
    rodada = 1
    sobras = "1" if e_80_20 else "2"
    denominador = f"Vagas_Sobras_{sobras}_Rodada_0"
    federacao[denominador] = federacao["Vagas"].copy()

    continuar = (len(eleitos) < vagas)

    while continuar:
        # Calcula a média. Se for rodada 1, pelo número de vagas conquistadas.
        # As demais pela média apenas para essa regra
        media = pd.Series(
            np.round((federacao["Votos"])/(federacao[denominador] + 1), 2))
        nome_col = f"Médias_Sobras {sobras}_Rodada " + str(rodada)
        federacao.insert(len(federacao.columns), nome_col, media)

        # Ordena por maior média na rodada a federação que atenda 80% do QE
        if e_80_20:
            federacao_maior_media = federacao[federacao["Maior que 80% QE"]].sort_values(
                nome_col, ascending=False).head(1)
        else:
            federacao_maior_media = federacao.sort_values(
                nome_col, ascending=False).head(1)

        # Acrescenta uma vaga para efeito de contagem dessa rodada para a federação escolhida
        denominador = f"Vagas_Sobras_{sobras}_Rodada_" + str(rodada)
        federacao[denominador] = federacao[f'''Vagas_Sobras_{
            sobras}_Rodada_''' + str(rodada-1)]

        federacao.loc[federacao_maior_media.index,
                      denominador] = federacao.loc[federacao_maior_media.index, denominador] + 1

        # Escolhe o primeiro candidato da federação que ganhou a vaga com mais de 20% de QE
        if e_80_20:
            candidato_eleito = candidatos_restantes[
                (candidatos_restantes["Maior que 20% QE"]) &
                (candidatos_restantes["Federação"] ==
                 federacao_maior_media.iloc[0].at["Federação"])
            ].head(1)
        else:
            candidato_eleito = candidatos_restantes[
                candidatos_restantes["Federação"] == federacao_maior_media.iloc[0].at["Federação"]
            ].head(1)

        if not candidato_eleito.empty:
            # Caso tenha escolhido mesmo um candidato,
            # soma mais um na vaga conquistada em geral mesmo
            federacao.loc[federacao_maior_media.index,
                          "Vagas"] = federacao.loc[federacao_maior_media.index, denominador]

            aux = pd.DataFrame(
                candidato_eleito[[e for e in eleitos.columns if e not in ["Regra", "Rodada"]]
                                 ]).reset_index(drop=True)

            aux["Regra"] = regra
            aux["Rodada"] = rodada

            eleitos = pd.concat([eleitos, aux])

            log.write(f'{regra_str}: Candidato eleito {aux.at[0, "Candidato"]} da \
federação {aux.at[0, "Federação"]} na rodada {rodada} \
com média {federacao_maior_media.iloc[0].at[nome_col]} \n')

            candidatos_restantes.drop(
                index=candidato_eleito.index, inplace=True)
        else:
            log.write(f'{regra_str}: Candidato não eleito da \
federação {federacao_maior_media.iloc[0].at["Federação"]} na rodada {rodada} \
com média {federacao_maior_media.iloc[0].at[nome_col]} \n')

        rodada = rodada + 1

        # Verifica se ainda existem candidatos e federações 80-20
        if e_80_20:
            continuar = (len(pd.merge(candidatos_restantes[
                candidatos_restantes["Maior que 20% QE"]],
                federacao[federacao["Maior que 80% QE"]],
                how="inner", on="Federação")) > 0)  # & continuar
            continuar = (len(eleitos) < vagas) & continuar
        else:
            continuar = continuar = (len(eleitos) < vagas) & (
                len(candidatos_restantes) > 0)

    return eleitos.reset_index(drop=True), federacao, candidatos_restantes


if __name__ == "__main__":
    vagas = int(open("vagas.txt", "r").read())
    bu = pd.read_csv("votos.csv", delimiter=";")
    bu.sort_values("Votos", ascending=False, inplace=True)

    candidatos_restantes, federacao = retorna_candidatos_federacao(bu, vagas)

    log = open("log.txt", "w")

    eleitos, candidatos_restantes = regra_1_qp(
        federacao[federacao["QP"] > 0], candidatos_restantes, log)
    eleitos, federacao, candidatos_restantes = regra_sobras(
        eleitos, vagas, federacao, candidatos_restantes, log)
    eleitos, federacao, candidatos_restantes = regra_sobras(
        eleitos, vagas, federacao, candidatos_restantes, log, False)

    log.close()

    eleitos.to_csv("eleitos.csv", index=False, sep=";")
    eleitos.to_excel("eleitos.xlsx", index=False)
    federacao.to_csv("federacao.csv", index=False, sep=";")
    federacao.to_excel("federacao.xlsx", index=False)
    with open("log.txt", "r") as log:
        print(log.read())
