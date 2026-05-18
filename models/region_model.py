import geobr
import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from pathlib import Path
from shapely.geometry import box
from functools import lru_cache

ESTADOS = [
    ("AC", "Acre"), ("AL", "Alagoas"), ("AP", "Amapá"), ("AM", "Amazonas"),
    ("BA", "Bahia"), ("CE", "Ceará"), ("DF", "Distrito Federal"),
    ("ES", "Espírito Santo"), ("GO", "Goiás"), ("MA", "Maranhão"),
    ("MT", "Mato Grosso"), ("MS", "Mato Grosso do Sul"), ("MG", "Minas Gerais"),
    ("PA", "Pará"), ("PB", "Paraíba"), ("PR", "Paraná"), ("PE", "Pernambuco"),
    ("PI", "Piauí"), ("RJ", "Rio de Janeiro"), ("RN", "Rio Grande do Norte"),
    ("RS", "Rio Grande do Sul"), ("RO", "Rondônia"), ("RR", "Roraima"),
    ("SC", "Santa Catarina"), ("SP", "São Paulo"), ("SE", "Sergipe"), ("TO", "Tocantins"),
]

CODIGOS_ESTADO = {
    "AC": 12, "AL": 27, "AP": 16, "AM": 13, "BA": 29, "CE": 23,
    "DF": 53, "ES": 32, "GO": 52, "MA": 21, "MT": 51, "MS": 50,
    "MG": 31, "PA": 15, "PB": 25, "PR": 41, "PE": 26, "PI": 22,
    "RJ": 33, "RN": 24, "RS": 43, "RO": 11, "RR": 14, "SC": 42,
    "SP": 35, "SE": 28, "TO": 17,
}


def preview_dataset(arquivo) -> dict:
    ds = _normalizar_coords(xr.open_dataset(arquivo, engine="h5netcdf"))
    res_lat = float(np.abs(np.diff(ds.lat.values).mean()))
    res_lon = float(np.abs(np.diff(ds.lon.values).mean()))
    return {
        "variaveis": list(ds.data_vars),
        "inicio": pd.Timestamp(ds.time.values[0]).date(),
        "fim": pd.Timestamp(ds.time.values[-1]).date(),
        "n_tempo": len(ds.time),
        "resolucao": f"{res_lat:.2f}° × {res_lon:.2f}°",
        "n_lat": ds.sizes["lat"],
        "n_lon": ds.sizes["lon"],
    }


@lru_cache(maxsize=27)
def carregar_municipios(abbrev_state: str) -> list[tuple[int, str]]:
    gdf = geobr.read_municipality(code_muni=abbrev_state, year=2022)
    return sorted(
        [(int(row.code_muni), row.name_muni) for _, row in gdf.iterrows()],
        key=lambda x: x[1],
    )


def get_boundary_estado(codigo) -> gpd.GeoDataFrame:
    try:
        codigo = int(codigo)
    except (ValueError, TypeError):
        pass
    return geobr.read_state(code_state=codigo, year=2020)


def get_boundary_municipio(codigo: int) -> gpd.GeoDataFrame:
    return geobr.read_municipality(code_muni=int(codigo), year=2022)


def _detectar_crs(ds: xr.Dataset) -> str:
    for var in ds.data_vars:
        gm = ds[var].attrs.get("grid_mapping")
        if gm and gm in ds:
            wkt = ds[gm].attrs.get("crs_wkt") or ds[gm].attrs.get("spatial_ref")
            if wkt:
                return wkt
    return "EPSG:4326"


def _normalizar_coords(ds: xr.Dataset) -> xr.Dataset:
    coords_lower = {c.lower(): c for c in ds.coords}
    renomear = {}
    if "latitude" in coords_lower and "lat" not in coords_lower:
        renomear[coords_lower["latitude"]] = "lat"
    if "longitude" in coords_lower and "lon" not in coords_lower:
        renomear[coords_lower["longitude"]] = "lon"
    return ds.rename(renomear) if renomear else ds


def abrir_dataset(arquivo) -> xr.Dataset:
    ds = xr.open_dataset(arquivo, engine="h5netcdf")
    return _normalizar_coords(ds)


def preview_dataset_info(arquivo) -> dict:
    return preview_dataset(arquivo)


def pontos_na_regiao(
    ds: xr.Dataset,
    variavel: str,
    boundary: gpd.GeoDataFrame,
    data_inicio=None,
    data_fim=None,
) -> tuple[pd.DataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    lats = ds.lat.values
    lons = ds.lon.values

    lat_grid, lon_grid = np.meshgrid(lats, lons, indexing="ij")
    lat_flat = lat_grid.ravel()
    lon_flat = lon_grid.ravel()

    crs_grid = _detectar_crs(ds)
    res_lat = float(np.abs(np.diff(lats).mean()))
    res_lon = float(np.abs(np.diff(lons).mean()))

    cells = [
        box(lon - res_lon / 2, lat - res_lat / 2, lon + res_lon / 2, lat + res_lat / 2)
        for lat, lon in zip(lat_flat, lon_flat)
    ]

    gdf_pontos = gpd.GeoDataFrame(
        {"lat": lat_flat, "lon": lon_flat}, geometry=cells, crs=crs_grid
    )

    boundary_reproj = boundary.to_crs(gdf_pontos.crs)
    dentro = gpd.sjoin(gdf_pontos, boundary_reproj[["geometry"]], how="inner", predicate="intersects")
    dentro = dentro[~dentro.index.duplicated(keep="first")]

    if dentro.empty:
        raise ValueError("Nenhum ponto do grid encontrado dentro da região selecionada.")

    dfs = []
    for _, row in dentro.iterrows():
        lat, lon = row["lat"], row["lon"]
        nome = f"lat{lat:.2f}_lon{lon:.2f}"
        serie = ds[variavel].sel(lat=lat, lon=lon)
        df_ponto = serie.to_dataframe()[[variavel]].rename(columns={variavel: nome})
        dfs.append(df_ponto)

    df_final = pd.concat(dfs, axis=1)
    df_final.index.name = "time"

    if data_inicio or data_fim:
        df_final = df_final.loc[
            (str(data_inicio) if data_inicio else slice(None)):
            (str(data_fim) if data_fim else slice(None))
        ]

    return df_final, dentro, boundary_reproj


def calcular_estatisticas(df: pd.DataFrame) -> pd.DataFrame:
    anuais = df.resample("YE").sum()
    stats = anuais.agg(["mean", "std", "min", "max"]).T
    stats.columns = ["Média Anual", "Desvio Padrão", "Mínimo Anual", "Máximo Anual"]
    stats.index.name = "Célula"
    return stats.round(2)


def calcular_media_regional(df: pd.DataFrame) -> pd.Series:
    serie = df.mean(axis=1)
    serie.name = "media_regional"
    return serie


def calcular_climatologia(serie: pd.Series) -> pd.Series:
    totais_mensais = serie.resample("ME").sum()
    climatologia = totais_mensais.groupby(totais_mensais.index.month).mean()
    climatologia.index = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
    return climatologia


def calcular_serie_anual(serie: pd.Series) -> pd.Series:
    return serie.resample("YE").sum().rename(lambda x: x.year)


