import streamlit as st
from controllers.grid_controller import run as run_grid

st.set_page_config(page_title="Mestrado", layout="wide")

modulos = {
    "Grid to CSV": run_grid,
}

with st.sidebar:
    st.title("Módulos")
    modulo_selecionado = st.radio(
        label="Navegação",
        options=list(modulos.keys()),
        label_visibility="collapsed",
    )

modulos[modulo_selecionado]()
