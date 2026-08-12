import pandas as pd
import plotly.express as px
import streamlit as st

from utils.data_loader import load_data

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
