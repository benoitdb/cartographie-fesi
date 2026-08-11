import pandas as pd
import plotly.express as px
import streamlit as st

from utils.data_loader import load_data, load_geojson

st.set_page_config(page_title="Cartographie FESI", layout="wide")

data = load_data()
geojson = load_geojson()

st.title("Cartographie des projets FESI - Vue Nationale")

# Bandeau KPI
total_montant = sum(v["montant_ue_total"] for v in data["aggregates"]["by_region"].values())
total_count = sum(v["count"] for v in data["aggregates"]["by_region"].values())
nb_regions = len(data["aggregates"]["by_region"])

col1, col2, col3 = st.columns(3)
col1.metric("Montant UE total", f"{total_montant / 1e6:,.1f} M€".replace(",", " "))
col2.metric("Nombre de projets", f"{total_count:,}".replace(",", " "))
col3.metric("Régions", nb_regions)

# Régions présentes dans le GeoJSON (métropole uniquement pour cette étape)
regions_metro = {f["properties"]["nom"] for f in geojson["features"]}

by_region = data["aggregates"]["by_region"]

DOM_TOM = ["Guadeloupe", "Guyane", "Martinique", "Mayotte", "La Réunion", "Saint-Martin"]
# TODO: remplacer par une icône contour réelle par territoire (pas de GeoJSON DOM-TOM disponible pour l'instant)
DOM_TOM_ICON = "🏝️"

map_col, domtom_col = st.columns([2, 1])

with map_col:
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

with domtom_col:
    st.subheader("DOM-TOM")
    for i in range(0, len(DOM_TOM), 2):
        row_territories = DOM_TOM[i : i + 2]
        cols = st.columns(2)
        for col, territory in zip(cols, row_territories):
            values = by_region.get(territory)
            with col:
                with st.container(border=True):
                    st.markdown(f"**{DOM_TOM_ICON} {territory}**")
                    if values:
                        st.caption(f"{values['montant_ue_total'] / 1e6:,.1f} M€ · {values['count']} projets".replace(",", " "))
                    else:
                        st.caption("Aucun projet")
