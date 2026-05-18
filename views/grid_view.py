import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from models.region_model import ESTADOS, CODIGOS_ESTADO, carregar_municipios



def render_arquivo() -> dict:
    st.title("Grid to CSV")
    arquivo = st.file_uploader("Arquivo NetCDF (.nc)", type=["nc"])
    return {"arquivo": arquivo}


def render_preview(info: dict):
    with st.expander("Informações do arquivo", expanded=True):
        col1, col2, col3 = st.columns(3)
        col1.metric("Resolução", info["resolucao"])
        col2.metric("Início", str(info["inicio"]))
        col3.metric("Fim", str(info["fim"]))
        col1.metric("Grade", f"{info['n_lat']} lat × {info['n_lon']} lon")
        col2.metric("Registros temporais", f"{info['n_tempo']:,}")


def render_regiao() -> dict:
    st.divider()
    st.subheader("Região de estudo")

    tipo = st.radio(
        "Tipo", ["Estado", "Município"],
        horizontal=True, label_visibility="collapsed",
    )

    opcoes_estado = [f"{nome} ({abbrev})" for abbrev, nome in ESTADOS]
    codigo = None

    if tipo == "Estado":
        escolha = st.selectbox("Estado", opcoes_estado)
        if escolha:
            abbrev = escolha.split("(")[1].rstrip(")")
            codigo = CODIGOS_ESTADO[abbrev]
    else:
        col1, col2 = st.columns(2)
        with col1:
            escolha_estado = st.selectbox("Estado", opcoes_estado)
            abbrev = escolha_estado.split("(")[1].rstrip(")")
        with col2:
            with st.spinner("Carregando municípios..."):
                municipios = carregar_municipios(abbrev)
            muni_map = {nome: code for code, nome in municipios}
            escolha_muni = st.selectbox("Município", list(muni_map.keys()))
            if escolha_muni:
                codigo = muni_map[escolha_muni]

    return {"tipo": tipo, "codigo": codigo}


def render_periodo(inicio, fim) -> tuple:
    st.divider()
    st.subheader("Período")
    col1, col2 = st.columns(2)
    with col1:
        data_inicio = st.date_input("Data início", value=inicio, min_value=inicio, max_value=fim)
    with col2:
        data_fim = st.date_input("Data fim", value=fim, min_value=inicio, max_value=fim)
    return data_inicio, data_fim


def render_resultado(df, pontos_gdf, boundary_gdf, stats, media_regional, climatologia, serie_anual):
    st.success(f"{len(df.columns)} célula(s) extraída(s) — {len(df)} registros cada.")

    # ── Mapa com cor por precipitação média ──────────────────────────────────
    st.subheader("Mapa — precipitação média por célula")

    cells_wgs = pontos_gdf.to_crs("EPSG:4326").copy()
    medias = df.mean()
    vmin, vmax = medias.min(), medias.max()

    cells_data = []
    for _, row in cells_wgs.iterrows():
        col_name = f"lat{row['lat']:.2f}_lon{row['lon']:.2f}"
        val = medias.get(col_name, np.nan)
        val = 0.0 if (val is None or np.isnan(val)) else float(val)
        norm = float((val - vmin) / (vmax - vmin)) if (vmax > vmin and not np.isnan(vmin) and not np.isnan(vmax)) else 0.0
        if np.isnan(norm):
            norm = 0.0
        r = int(210 - 180 * norm)
        g = int(230 - 180 * norm)
        b = 255
        cells_data.append({
            "polygon": list(row.geometry.exterior.coords),
            "media": round(val, 3),
            "cor": [r, g, b, 180],
        })

    center_lon = float(cells_wgs.geometry.centroid.x.mean())
    center_lat = float(cells_wgs.geometry.centroid.y.mean())

    st.pydeck_chart(pdk.Deck(
        layers=[
            pdk.Layer(
                "PolygonLayer",
                data=cells_data,
                get_polygon="polygon",
                get_fill_color="cor",
                get_line_color=[100, 100, 100, 100],
                line_width_min_pixels=1,
                pickable=True,
                auto_highlight=True,
            ),
            pdk.Layer(
                "GeoJsonLayer",
                data=boundary_gdf.to_crs("EPSG:4326").__geo_interface__,
                stroked=True, filled=False,
                get_line_color=[43, 90, 24, 255],
                line_width_min_pixels=2,
            ),
        ],
        initial_view_state=pdk.ViewState(
            longitude=center_lon, latitude=center_lat, zoom=5, pitch=0
        ),
        map_style="light",
        height=400,
        tooltip={"text": "Média: {media}"},
    ))

    # ── Ciclo anual médio ─────────────────────────────────────────────────────
    st.subheader("Ciclo anual médio — precipitação total mensal projetada")
    fig_clim = px.bar(
        x=climatologia.index,
        y=climatologia.values,
        labels={"x": "Mês", "y": "Precipitação total média"},
        color=climatologia.values,
        color_continuous_scale="Blues",
    )
    fig_clim.update_layout(coloraxis_showscale=False, height=350, margin=dict(t=20))
    st.plotly_chart(fig_clim, use_container_width=True)

    # ── Série temporal anual ──────────────────────────────────────────────────
    st.subheader("Série temporal — precipitação total anual projetada (2015–2100)")
    fig_anual = px.line(
        x=serie_anual.index,
        y=serie_anual.values,
        labels={"x": "Ano", "y": "Precipitação total anual"},
        markers=False,
    )
    fig_anual.update_traces(line_color="#1f77b4")
    fig_anual.update_layout(height=350, margin=dict(t=20))
    st.plotly_chart(fig_anual, use_container_width=True)

    # ── Estatísticas ──────────────────────────────────────────────────────────
    with st.expander("Estatísticas por célula"):
        st.dataframe(stats, use_container_width=True)

    # ── Download ──────────────────────────────────────────────────────────────
    st.divider()
    df_export = pd.concat([media_regional, df], axis=1)

    col1, col2 = st.columns([2, 1])
    with col1:
        nome = st.text_input("Nome do arquivo", value="output")
    nome_csv = (nome.strip() if nome.strip().endswith(".csv") else nome.strip() + ".csv")
    with col2:
        st.write("")
        st.write("")
        st.download_button(
            label="Baixar CSV",
            data=df_export.to_csv().encode("utf-8"),
            file_name=nome_csv,
            mime="text/csv",
            type="primary",
            use_container_width=True,
        )


def render_erro(mensagem: str):
    st.error(mensagem)


def render_rodape():
    st.divider()
    st.caption(
        "Desenvolvido por **Victor Rodrigues Shiraishi** · "
        "[victor.shiraishi@ufpr.br](mailto:victor.shiraishi@ufpr.br)"
    )
