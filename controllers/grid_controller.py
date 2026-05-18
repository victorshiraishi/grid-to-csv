import streamlit as st
from models.region_model import (
    preview_dataset,
    abrir_dataset,
    get_boundary_estado,
    get_boundary_municipio,
    pontos_na_regiao,
    calcular_estatisticas,
    calcular_media_regional,
    calcular_climatologia,
    calcular_serie_anual,
)
from views.grid_view import (
    render_arquivo,
    render_preview,
    render_regiao,
    render_periodo,
    render_resultado,
    render_erro,
    render_rodape,
)


@st.cache_data(show_spinner=False)
def _preview_cache(arquivo) -> dict:
    return preview_dataset(arquivo)


@st.cache_data(hash_funcs={"geopandas.geodataframe.GeoDataFrame": lambda _: None})
def _boundary_estado_cache(codigo):
    return get_boundary_estado(codigo)


@st.cache_data(hash_funcs={"geopandas.geodataframe.GeoDataFrame": lambda _: None})
def _boundary_municipio_cache(codigo: int):
    return get_boundary_municipio(codigo)


def run():
    # 1. Upload + preview
    preview = None
    arquivo_inputs = render_arquivo()
    arquivo = arquivo_inputs["arquivo"]
    variavel = None

    if arquivo:
        try:
            preview = _preview_cache(arquivo)
            render_preview(preview)
            variavel = st.selectbox("Variável", preview["variaveis"])
        except Exception as e:
            render_erro(f"Erro ao ler o arquivo: {e}")
            render_rodape()
            return

    # 2. Região
    regiao = render_regiao()

    # 3. Período
    data_inicio = data_fim = None
    if preview:
        data_inicio, data_fim = render_periodo(preview["inicio"], preview["fim"])

    # 4. Botão
    st.divider()
    rodar = st.button("Converter", type="primary")
    render_rodape()

    if not rodar:
        return

    if not arquivo:
        render_erro("Faça upload do arquivo NetCDF.")
        return
    if not regiao["codigo"]:
        render_erro("Selecione uma região válida.")
        return

    # Carrega boundary
    with st.spinner("Carregando limite geográfico..."):
        try:
            if regiao["tipo"] == "Estado":
                boundary = _boundary_estado_cache(regiao["codigo"])
            else:
                boundary = _boundary_municipio_cache(int(regiao["codigo"]))
        except Exception as e:
            render_erro(f"Região não encontrada: {e}")
            return

    # Extrai
    with st.spinner("Extraindo pontos do grid..."):
        try:
            arquivo.seek(0)
            ds = abrir_dataset(arquivo)
            if variavel not in ds:
                render_erro(f"Variável '{variavel}' não encontrada. Disponíveis: {list(ds.data_vars)}")
                return
            df, pontos_gdf, boundary_reproj = pontos_na_regiao(
                ds, variavel, boundary, data_inicio, data_fim
            )
        except ValueError as e:
            render_erro(str(e))
            return
        except Exception as e:
            render_erro(f"Erro ao processar: {e}")
            return

    stats          = calcular_estatisticas(df)
    media_regional = calcular_media_regional(df)
    climatologia   = calcular_climatologia(media_regional)
    serie_anual    = calcular_serie_anual(media_regional)

    render_resultado(df, pontos_gdf, boundary_reproj, stats,
                     media_regional, climatologia, serie_anual)
