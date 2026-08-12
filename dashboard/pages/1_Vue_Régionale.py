import pandas as pd
import plotly.express as px
import streamlit as st

from utils.data_loader import load_data
from utils.treemap import build_hierarchy_treemap

FONDS, LEVEL1, LEVEL2, LEVEL3 = "Fonds", "Objectif stratégique", "Objectif spécifique (Code et libellé)", "Type d'intervention"

st.set_page_config(page_title="Vue Régionale - Cartographie FESI", layout="wide")

data = load_data()
by_region = data["aggregates"]["by_region"]
by_region_fonds = data["aggregates"]["by_region_fonds"]

# "Volet national" n'est pas une région géographique : listé à part, en fin de sélecteur
regions = sorted(r for r in by_region if r != "Volet national") + ["Volet national"]

region = st.selectbox("Région", regions)

st.title(f"Vue Régionale - {region}")

region_data = by_region[region]

col1, col2, col3 = st.columns(3)
col1.metric("Montant UE total", f"{region_data['montant_ue_total'] / 1e6:,.1f} M€".replace(",", " "))
col2.metric("Nombre de projets", f"{region_data['count']:,}".replace(",", " "))
col3.metric("Montant UE moyen", f"{region_data['montant_ue_moyen'] / 1e3:,.0f} k€".replace(",", " "))

# Répartition par fonds
st.subheader("Répartition par fonds")

df_region_fonds = pd.DataFrame(
    [
        {"fonds": v["fonds"], "montant_ue_total": v["montant_ue_total"], "count": v["count"]}
        for key, v in by_region_fonds.items()
        if v["region"] == region
    ]
).sort_values("montant_ue_total")

fig_region_fonds = px.bar(
    df_region_fonds,
    x="montant_ue_total",
    y="fonds",
    orientation="h",
    color="fonds",
    hover_data=["count"],
    labels={"montant_ue_total": "Montant UE (€)", "fonds": "Fonds", "count": "Nb projets"},
)
fig_region_fonds.update_layout(height=250, showlegend=False)
fig_region_fonds.update_traces(width=0.5)

st.plotly_chart(fig_region_fonds, use_container_width=True)

if region == "Volet national":
    region_ops = [op for op in data["operations"] if op.get("is_national")]
else:
    region_ops = [
        op
        for op in data["operations"]
        if op.get("regions_modernes") == [region] and not op.get("is_interregional") and not op.get("is_national")
    ]

df_region_ops = pd.DataFrame(region_ops)
df_region_ops[LEVEL1] = df_region_ops[LEVEL1].fillna("Non spécifié")
df_region_ops[LEVEL2] = df_region_ops[LEVEL2].fillna("Non spécifié")
df_region_ops[LEVEL3] = df_region_ops[LEVEL3].fillna("Non spécifié")

# Vue d'ensemble : fonds > objectif stratégique > objectif spécifique
st.subheader("Fonds, objectifs stratégiques et spécifiques")

fig_hierarchy = build_hierarchy_treemap(df_region_ops, [FONDS, LEVEL1, LEVEL2])

st.plotly_chart(fig_hierarchy, use_container_width=True)

# Détail par fonds : objectif stratégique > spécifique > type d'intervention
st.subheader("Détail par fonds")

fonds_presents = sorted(df_region_ops[FONDS].unique())
fonds_cols = st.columns(len(fonds_presents))

for col, fonds in zip(fonds_cols, fonds_presents):
    with col:
        st.markdown(f"**{fonds}**")
        df_fonds = df_region_ops[df_region_ops[FONDS] == fonds]
        fig_fonds_detail = build_hierarchy_treemap(df_fonds, [LEVEL1, LEVEL2, LEVEL3])
        st.plotly_chart(fig_fonds_detail, use_container_width=True)

# Courbe cumulée d'engagement UE dans le temps
st.subheader("Engagement UE cumulé dans le temps")
st.caption(
    "Basé sur la date de début de l'opération. Environ 60% des dates sont arrondies au 1ᵉʳ janvier "
    "(date administrative/programmatique plutôt qu'une date de démarrage individuelle précise) : "
    "la courbe présente donc des paliers plutôt qu'une progression lissée."
)

st.caption("Cliquer sur un fonds dans la légende pour l'isoler ou le masquer.")

df_dates = df_region_ops[["Date de début de l'opération", "Montant UE", "Fonds"]].copy()
df_dates["Date de début de l'opération"] = pd.to_datetime(df_dates["Date de début de l'opération"])
df_dates = (
    df_dates.groupby(["Fonds", "Date de début de l'opération"], as_index=False)["Montant UE"]
    .sum()
    .sort_values(["Fonds", "Date de début de l'opération"])
)
df_dates["cumule"] = df_dates.groupby("Fonds")["Montant UE"].cumsum()

fig_cumul = px.line(
    df_dates,
    x="Date de début de l'opération",
    y="cumule",
    color="Fonds",
    labels={"Date de début de l'opération": "Date", "cumule": "Montant UE cumulé (€)"},
)
fig_cumul.update_traces(line=dict(width=2))

for year in range(
    df_dates["Date de début de l'opération"].dt.year.min(), df_dates["Date de début de l'opération"].dt.year.max() + 1
):
    fig_cumul.add_vline(x=f"{year}-01-01", line_dash="dot", line_color="gray", opacity=0.4)

st.plotly_chart(fig_cumul, use_container_width=True)
