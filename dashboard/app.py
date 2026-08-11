import pandas as pd
import plotly.express as px
import streamlit as st

from utils.data_loader import load_data, load_geojson

st.set_page_config(page_title="Cartographie FESI", layout="wide")

data = load_data()
geojson = load_geojson()

st.title("Cartographie des projets FESI - Vue Nationale")

# Régions présentes dans le GeoJSON (métropole uniquement pour cette étape)
regions_metro = {f["properties"]["nom"] for f in geojson["features"]}

by_region = data["aggregates"]["by_region"]
rows = [
    {"region": region, "montant_ue_total": values["montant_ue_total"], "count": values["count"]}
    for region, values in by_region.items()
    if region in regions_metro
]
df = pd.DataFrame(rows)

fig = px.choropleth(
    df,
    geojson=geojson,
    locations="region",
    featureidkey="properties.nom",
    color="montant_ue_total",
    color_continuous_scale="Blues",
    hover_data=["count"],
    labels={"montant_ue_total": "Montant UE (€)", "count": "Nb projets"},
)
fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})

st.plotly_chart(fig, use_container_width=True)
