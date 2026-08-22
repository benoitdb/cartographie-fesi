import pandas as pd
import plotly.express as px
import streamlit as st

from utils.data_loader import load_data, load_programme_totals, load_region_metadata
from utils.filters import FONDS_OPTIONS, render_fonds_filter, summarize_ops
from utils.plot_style import style_hover
from utils.themes import FONDS_COLORS

st.set_page_config(page_title="Comparateur - Cartographie FESI", layout="wide")

RESERVE_METHODO_COURTE = (
    "⚠️ Enveloppe programmée = Accord de partenariat, Tableau 9B (dotations préliminaires, "
    "version adoptée le 2 juin 2022) — taux de consommation estimatif, pas un chiffre "
    "d'exécution officiel."
)


def get_region_ops(data, region, selected_fonds):
    return [
        op
        for op in data["operations"]
        if op.get("regions_modernes") == [region]
        and not op.get("is_interregional")
        and not op.get("is_national")
        and op.get("Fonds") in selected_fonds
    ]


def render_region_column(region, region_ops, by_region, region_metadata, programme_totals, selected_fonds, filtre_actif):
    st.subheader(region)

    if not region_ops:
        st.info("Aucune opération pour cette région avec les fonds sélectionnés.")
        return

    region_data = summarize_ops(region_ops) if filtre_actif else by_region.get(region, summarize_ops(region_ops))
    region_meta = region_metadata.get(region)

    with st.container(border=True):
        st.markdown(f"**Montant UE total :** {region_data['montant_ue_total'] / 1e6:,.1f} M€".replace(",", " "))
        st.markdown(f"**Nombre de projets :** {region_data['count']:,}".replace(",", " "))
        st.markdown(f"**Montant UE moyen :** {region_data['montant_ue_moyen'] / 1e3:,.0f} k€".replace(",", " "))
        if region_meta:
            montant_par_habitant = region_data["montant_ue_total"] / region_meta["population"]
            st.markdown(f"**Montant UE / habitant :** {montant_par_habitant:,.0f} €".replace(",", " "))

    # Répartition par fonds — barres horizontales compactes, une couleur par fonds (même
    # palette que le reste du dashboard), pas de courbe cumulée ni de treemap ici : le
    # comparateur reste volontairement condensé pour tenir en demi-largeur (issue #32).
    df_region = pd.DataFrame(region_ops)
    df_fonds = df_region.groupby("Fonds")["Montant UE"].sum().reset_index().sort_values("Montant UE")
    fig_fonds = px.bar(
        df_fonds,
        x="Montant UE",
        y="Fonds",
        color="Fonds",
        color_discrete_map=FONDS_COLORS,
        orientation="h",
        labels={"Montant UE": "Montant UE (€)", "Fonds": ""},
    )
    fig_fonds.update_layout(height=200, showlegend=False, margin=dict(l=0, r=0, t=10, b=0))
    fig_fonds.for_each_trace(lambda t: t.update(hovertemplate=f"<b>{t.name}</b><br>Montant UE : %{{x:,.0f}} €<extra></extra>"))
    fig_fonds = style_hover(fig_fonds)
    st.plotly_chart(fig_fonds, use_container_width=True)

    # Taux de consommation — version condensée de render_kpi_pilotage (utils/pilotage.py) :
    # une seule barre de progression globale plutôt qu'une card par fonds, pour ne pas
    # imbriquer 3 sous-colonnes dans une colonne déjà à demi-largeur (peu lisible).
    programme_totals_region = programme_totals.get(region, {})
    montant_programme = sum(v for f, v in programme_totals_region.items() if f in selected_fonds)
    if montant_programme:
        taux = region_data["montant_ue_total"] / montant_programme
        st.progress(min(taux, 1.0), text=f"Consommé : {taux:.0%} de l'enveloppe programmée")
        if taux > 1:
            st.caption("⚠️ Dépassement > 100% possible sur le FSE+ (transfert national → régional non tracé).")
    else:
        st.caption("Pas d'enveloppe programmée pour cette sélection de fonds.")


data = load_data()
by_region = data["aggregates"]["by_region"]
region_metadata = load_region_metadata()
programme_totals = load_programme_totals()

selected_fonds = render_fonds_filter()
filtre_actif = set(selected_fonds) != set(FONDS_OPTIONS)

st.title("Comparateur régional")
st.caption(
    "Deux régions choisies, indicateurs clés en miroir — vue condensée, pour l'analyse complète "
    "d'une région voir Vue Régionale. " + RESERVE_METHODO_COURTE
)

regions_disponibles = sorted(by_region)
select_col_a, select_col_b = st.columns(2)
with select_col_a:
    region_a = st.selectbox("Région A", regions_disponibles, index=0, key="comparateur_region_a")
with select_col_b:
    index_b = 1 if len(regions_disponibles) > 1 else 0
    region_b = st.selectbox("Région B", regions_disponibles, index=index_b, key="comparateur_region_b")

col_a, col_b = st.columns(2)
with col_a:
    render_region_column(
        region_a, get_region_ops(data, region_a, selected_fonds), by_region, region_metadata, programme_totals, selected_fonds, filtre_actif
    )
with col_b:
    render_region_column(
        region_b, get_region_ops(data, region_b, selected_fonds), by_region, region_metadata, programme_totals, selected_fonds, filtre_actif
    )
