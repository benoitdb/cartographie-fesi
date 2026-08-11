import streamlit as st

from utils.data_loader import load_data

st.set_page_config(page_title="Vue Régionale - Cartographie FESI", layout="wide")

data = load_data()
by_region = data["aggregates"]["by_region"]

# "Volet national" n'est pas une région géographique, exclu du sélecteur
regions = sorted(r for r in by_region if r != "Volet national")

region = st.selectbox("Région", regions)

st.title(f"Vue Régionale - {region}")

region_data = by_region[region]

col1, col2, col3 = st.columns(3)
col1.metric("Montant UE total", f"{region_data['montant_ue_total'] / 1e6:,.1f} M€".replace(",", " "))
col2.metric("Nombre de projets", f"{region_data['count']:,}".replace(",", " "))
col3.metric("Montant UE moyen", f"{region_data['montant_ue_moyen'] / 1e3:,.0f} k€".replace(",", " "))
