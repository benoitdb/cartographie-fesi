import pandas as pd
import plotly.express as px
import streamlit as st

from utils.data_loader import load_data, load_geojson
from utils.filters import FONDS_OPTIONS, compute_by_region, render_fonds_filter, summarize_ops
from utils.treemap import build_hierarchy_treemap

FONDS, LEVEL1, LEVEL2 = "Fonds", "Objectif stratégique", "Objectif spécifique (Code et libellé)"

st.set_page_config(page_title="Cartographie FESI", layout="wide")

data = load_data()
geojson = load_geojson()

selected_fonds = render_fonds_filter()
filtre_actif = set(selected_fonds) != set(FONDS_OPTIONS)

st.title("Cartographie des projets FESI - Vue Nationale")

# Régions présentes dans le GeoJSON (métropole uniquement pour cette étape)
regions_metro = {f["properties"]["nom"] for f in geojson["features"]}

if filtre_actif:
    ops_selected = [op for op in data["operations"] if op.get("Fonds") in selected_fonds]
    by_region = compute_by_region(ops_selected)
else:
    # Fonds par défaut (tous sélectionnés) : agrégats pré-calculés du pipeline, comportement inchangé
    by_region = data["aggregates"]["by_region"]

# Bandeau KPI
total_montant = sum(v["montant_ue_total"] for v in by_region.values())
total_count = sum(v["count"] for v in by_region.values())
nb_regions = len(by_region)

col1, col2, col3 = st.columns(3)
col1.metric("Montant UE total", f"{total_montant / 1e6:,.1f} M€".replace(",", " "))
col2.metric("Nombre de projets", f"{total_count:,}".replace(",", " "))
col3.metric("Régions", nb_regions)

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

# Répartition par fonds
st.subheader("Répartition par fonds")

by_fonds = data["aggregates"]["by_fonds"]
df_fonds = pd.DataFrame(
    [
        {"fonds": fonds, "montant_ue_total": v["montant_ue_total"], "count": v["count"]}
        for fonds, v in by_fonds.items()
        if fonds in selected_fonds
    ]
).sort_values("montant_ue_total")

fig_fonds = px.bar(
    df_fonds,
    x="montant_ue_total",
    y="fonds",
    orientation="h",
    color="fonds",
    hover_data=["count"],
    labels={"montant_ue_total": "Montant UE (€)", "fonds": "Fonds", "count": "Nb projets"},
)
fig_fonds.update_layout(height=250, showlegend=False)
fig_fonds.update_traces(width=0.5)

st.plotly_chart(fig_fonds, use_container_width=True)

# Fonds, objectifs stratégiques et spécifiques
st.subheader("Fonds, objectifs stratégiques et spécifiques")

df_national_ops = pd.DataFrame([op for op in data["operations"] if op.get("Fonds") in selected_fonds])
df_national_ops[LEVEL1] = df_national_ops[LEVEL1].fillna("Non spécifié")
df_national_ops[LEVEL2] = df_national_ops[LEVEL2].fillna("Non spécifié")

fig_hierarchy = build_hierarchy_treemap(df_national_ops, [FONDS, LEVEL1, LEVEL2])

st.plotly_chart(fig_hierarchy, use_container_width=True)

# Volet national
st.subheader("Volet national")

national_ops = [op for op in data["operations"] if op.get("is_national") and op.get("Fonds") in selected_fonds]

if not national_ops:
    st.info("Aucune opération du Volet national pour les fonds sélectionnés.")
else:
    national = summarize_ops(national_ops)
    col1, col2 = st.columns(2)
    col1.metric("Montant UE total", f"{national['montant_ue_total'] / 1e6:,.1f} M€".replace(",", " "))
    col2.metric("Nombre de projets", f"{national['count']:,}".replace(",", " "))

    df_national_fonds = (
        pd.DataFrame(national_ops)
        .groupby("Fonds")
        .agg(montant_ue_total=("Montant UE", "sum"), count=("Montant UE", "count"))
        .reset_index()
        .sort_values("montant_ue_total")
    )

    fig_national_fonds = px.bar(
        df_national_fonds,
        x="montant_ue_total",
        y="Fonds",
        orientation="h",
        color="Fonds",
        hover_data=["count"],
        labels={"montant_ue_total": "Montant UE (€)", "count": "Nb projets"},
    )
    fig_national_fonds.update_layout(height=200, showlegend=False)
    fig_national_fonds.update_traces(width=0.5)

    st.plotly_chart(fig_national_fonds, use_container_width=True)

    # Courbe cumulée d'engagement UE dans le temps (Volet national)
    st.subheader("Engagement UE cumulé dans le temps")
    st.caption(
        "Basé sur la date de début de l'opération. Environ 60% des dates sont arrondies au 1ᵉʳ janvier "
        "(date administrative/programmatique plutôt qu'une date de démarrage individuelle précise) : "
        "la courbe présente donc des paliers plutôt qu'une progression lissée."
    )
    st.caption("Cliquer sur un fonds dans la légende pour l'isoler ou le masquer.")

    df_national_dates = pd.DataFrame(national_ops)[["Date de début de l'opération", "Montant UE", "Fonds"]].copy()
    df_national_dates["Date de début de l'opération"] = pd.to_datetime(df_national_dates["Date de début de l'opération"])
    df_national_dates = (
        df_national_dates.groupby(["Fonds", "Date de début de l'opération"], as_index=False)["Montant UE"]
        .sum()
        .sort_values(["Fonds", "Date de début de l'opération"])
    )
    df_national_dates["cumule"] = df_national_dates.groupby("Fonds")["Montant UE"].cumsum()

    fig_national_cumul = px.line(
        df_national_dates,
        x="Date de début de l'opération",
        y="cumule",
        color="Fonds",
        labels={"Date de début de l'opération": "Date", "cumule": "Montant UE cumulé (€)"},
    )
    fig_national_cumul.update_traces(line=dict(width=2))

    for year in range(
        df_national_dates["Date de début de l'opération"].dt.year.min(),
        df_national_dates["Date de début de l'opération"].dt.year.max() + 1,
    ):
        fig_national_cumul.add_vline(x=f"{year}-01-01", line_dash="dot", line_color="gray", opacity=0.4)

    st.plotly_chart(fig_national_cumul, use_container_width=True)
