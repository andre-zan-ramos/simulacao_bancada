import streamlit as st
import pandas as pd
import calcular_bancada as cb

st.set_page_config(
    page_title="Simulação de Bancada",
    page_icon=":material/groups:",
)

df_candidatos = pd.DataFrame(
    columns=["Candidato", "Partido", "Votos"])

tipo_tabela = "dynamic"

with st.expander("Upload de arquivo .csv"):
    a, b, a = st.columns([1, 4, 1])
    uploaded_file = b.file_uploader("", type=["csv"])

    if uploaded_file is not None:
        try:
            sep = "," if uploaded_file.readline().find(b',') > 0 else ";"
            uploaded_file.seek(0)
            df_candidatos = pd.read_csv(uploaded_file, sep=sep)
        except BaseException:
            st.warning(
                "Arquivo não está no padrão da tabela abaixo. Não foi carregado.")

        tipo_tabela = "fixed"

a, b, c = st.columns([3, 2, 2])
procurar = b.text_input("Procurar: ")

if procurar:
    mask = df_candidatos.applymap(
        lambda x: procurar.lower() in str(x).lower()).any(axis=1)
    df_candidatos = df_candidatos[mask]

excluir = c.text_input("Excluir: ")

if excluir:
    mask = df_candidatos.applymap(
        lambda x: excluir.lower() not in str(x).lower()).all(axis=1)
    df_candidatos = df_candidatos[mask]


@st.fragment()
def tabelas(df_candidatos):
    total = '{:n}'.format(df_candidatos["Votos"].sum())

    formatado = df_candidatos.copy()
    formatado['Votos'] = formatado['Votos'].map('{:n}'.format)

    bu = st.data_editor(
        formatado, use_container_width=True, num_rows=tipo_tabela, hide_index=True)

    a, b = st.columns([2, 1])
    b.info(f'**Total:** {total}')

    return bu


bu = tabelas(df_candidatos)

st.divider()

col1, col2, a, col3 = st.columns(4, vertical_alignment="center")

col1.write("Número de vagas:")

vagas = col2.number_input(
    "vagas", min_value=1, value=21, label_visibility="collapsed")

if col3.button("Simular a bancada", use_container_width=True):
    bu.sort_values("Votos", ascending=False, inplace=True)

    candidatos_restantes, federacao = cb.retorna_candidatos_federacao(
        bu, vagas)

    log = open("log.txt", "w")

    eleitos, candidatos_restantes = cb.regra_1_qp(
        federacao[federacao["QP"] > 0], candidatos_restantes, log)
    eleitos, federacao, candidatos_restantes = cb.regra_sobras(
        eleitos, vagas, federacao, candidatos_restantes, log)
    eleitos, federacao, candidatos_restantes = cb.regra_sobras(
        eleitos, vagas, federacao, candidatos_restantes, log, False)

    log.close()

    column_config = {
        "widgets": st.column_config.Column(
            "Streamlit Widgets",
            help="Streamlit **widget** commands 🎈",
            width="medium",
            required=True,
        )
    },

    st.divider()

    st.header("Eleitos")
    st.dataframe(eleitos, hide_index=True)

    st.header("Federação")
    st.dataframe(federacao, hide_index=True)

    with open("log.txt", "r") as log:
        texto = []
        for line in log:
            texto.append(line)

        with st.container(height=300, border=False).expander("Log das rodadas"):
            st.text(''.join(texto))
