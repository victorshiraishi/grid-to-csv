# Grid to CSV

Aplicação web para extração de dados de modelos climáticos em formato NetCDF para CSV, com recorte espacial por estado ou município brasileiro.

## Funcionalidades

- Upload de arquivos NetCDF (MSWEP, CLIMBRA e outros)
- Seleção de região por estado ou município (contorno oficial IBGE via geobr)
- Recorte espacial: extrai todas as células do grid que intersectam o contorno selecionado
- Filtro por período
- Visualização interativa das células extraídas no mapa
- Gráfico de ciclo anual médio (precipitação total mensal)
- Gráfico de série temporal anual (2015–2100)
- Estatísticas por célula (total anual médio, desvio padrão, mínimo e máximo)
- Download do CSV com a média regional e todas as células individuais

## Estrutura

```
grid-to-csv/
├── app.py                      # Entry point Streamlit
├── requirements.txt
├── .streamlit/
│   └── config.toml             # Limite de upload (5 GB)
├── models/
│   └── region_model.py         # Lógica de dados (xarray, geobr, geopandas)
├── views/
│   └── grid_view.py            # Interface (pydeck, plotly)
└── controllers/
    └── grid_controller.py      # Orquestração e cache
```

## Formatos suportados

| Formato | Coordenadas | Variável |
|---------|-------------|----------|
| MSWEP   | `lat`, `lon` | `pr` |
| CLIMBRA | `latitude`, `longitude` | `pr` |

Outros formatos com coordenadas `lat`/`lon` ou `latitude`/`longitude` e índice temporal `time` também são compatíveis.

## Instalação local

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Deploy (Streamlit Cloud)

1. Faça fork ou clone este repositório para sua conta GitHub
2. Acesse [share.streamlit.io](https://share.streamlit.io)
3. Conecte o repositório e defina `app.py` como arquivo principal
4. Clique em **Deploy**

## Desenvolvido por

**Victor Rodrigues Shiraishi** — [victor.shiraishi@ufpr.br](mailto:victor.shiraishi@ufpr.br)
