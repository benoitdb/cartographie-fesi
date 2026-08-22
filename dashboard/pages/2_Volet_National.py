import pandas as pd
import streamlit as st

from utils.data_loader import (
    load_data,
    load_programme_detail,
    load_programme_totals,
    load_region_metadata,
)
from utils.filters import FONDS_OPTIONS, render_fonds_filter, summarize_ops
from utils.pilotage import build_ranking_programme_vs_engage, build_trajectoire, render_kpi_pilotage
from utils.region_analysis import render_region_audit, render_region_ensemble, render_region_gestion

st.set_page_config(page_title="Volet National - Cartographie FESI", layout="wide")

data = load_data()

selected_fonds = render_fonds_filter()
filtre_actif = set(selected_fonds) != set(FONDS_OPTIONS)

st.title("Volet National")
st.caption(
    "Opérations FEDER/FSE+/FTJ non rattachées à une région : programmes nationaux (ex. "
    "opérations France Travail pour l'emploi, financées par le FSE+)."
)

national_ops = [op for op in data["operations"] if op.get("is_national") and op.get("Fonds") in selected_fonds]

if not national_ops:
    st.info("Aucune opération du Volet national pour les fonds sélectionnés.")
    st.stop()

if filtre_actif:
    national_data = summarize_ops(national_ops)
else:
    # Fonds par défaut (tous sélectionnés) : agrégat pré-calculé du pipeline, comportement inchangé
    national_data = data["aggregates"]["national"]

# Bandeau contexte : pas de chef-lieu/superficie (pas une région géographique), remplacés par
# des repères pertinents pour un volet national — population (pour le ratio par habitant, même
# source Wikidata que les Vues Régionales) et le poids de ce volet dans l'ensemble FESI.
population_totale = sum(v["population"] for v in load_region_metadata().values() if v["population"])
beneficiaires_distincts = len({op.get("Nom du bénéficiaire") for op in national_ops})
montant_tous_perimetres = sum(op["Montant UE"] for op in data["operations"] if op.get("Fonds") in selected_fonds)
part_national = national_data["montant_ue_total"] / montant_tous_perimetres if montant_tous_perimetres else 0

meta_col1, meta_col2, meta_col3 = st.columns(3)
with meta_col1:
    with st.container(border=True):
        st.markdown(f"**Population (France) :** {population_totale:,}".replace(",", " "))
with meta_col2:
    with st.container(border=True):
        st.markdown(f"**Bénéficiaires distincts :** {beneficiaires_distincts:,}".replace(",", " "))
with meta_col3:
    with st.container(border=True):
        st.markdown(f"**Part du total FESI national :** {part_national:.1%}")
st.caption(
    "Population : somme des populations régionales (source Wikidata, voir Vues Régionales). "
    "Part du total FESI national : poids du Volet national dans l'ensemble FEDER/FSE+/FTJ "
    "(régions + interrégional + national), pour les fonds sélectionnés."
)

col1, col2, col3, col4 = st.columns(4)
with col1:
    with st.container(border=True):
        st.markdown(f"**Montant UE total :** {national_data['montant_ue_total'] / 1e6:,.1f} M€".replace(",", " "))
with col2:
    with st.container(border=True):
        st.markdown(f"**Nombre de projets :** {national_data['count']:,}".replace(",", " "))
with col3:
    with st.container(border=True):
        st.markdown(f"**Montant UE moyen :** {national_data['montant_ue_moyen'] / 1e3:,.0f} k€".replace(",", " "))
if population_totale:
    with col4:
        with st.container(border=True):
            st.markdown(f"**Montant UE / habitant :** {national_data['montant_ue_total'] / population_totale:,.2f} €".replace(",", " "))

programme_totals_national = load_programme_totals().get("national", {})
montant_programme_national = sum(v for f, v in programme_totals_national.items() if f in selected_fonds)

tab_ensemble, tab_pilotage, tab_audit = st.tabs(["Vue d'ensemble", "Pilotage", "Analyses & contrôle"])

with tab_ensemble:
    df_national_analysis_ops = render_region_ensemble(
        national_ops,
        "le Volet national",
        key_suffix="_volet_national",
        programme_totals={f: v for f, v in programme_totals_national.items() if f in selected_fonds},
    )

with tab_pilotage:
    # Pilotage : programmé (Tableau 9B, Accord de partenariat 2021-2027) vs engagé (data.json)
    st.subheader("Pilotage : programmé vs engagé")

    if montant_programme_national:
        engage_by_fonds_national = pd.DataFrame(national_ops).groupby("Fonds")["Montant UE"].sum().to_dict()
        df_fonds_pilotage_national = pd.DataFrame(
            [
                {"fonds": f, "engage": engage_by_fonds_national.get(f, 0), "programme": programme_totals_national[f]}
                for f in ("FEDER", "FSE+", "FTJ")
                if f in programme_totals_national
            ]
        )
        programme_detail_national = load_programme_detail()
        render_kpi_pilotage(
            df_fonds_pilotage_national,
            montant_programme_national,
            national_data["montant_ue_total"],
            ftj_article=programme_detail_national["ftj_article"].get("national") if "FTJ" in selected_fonds else None,
            assistance_technique={
                f: v for f, v in programme_detail_national["assistance_technique"].get("national", {}).items() if f in selected_fonds
            },
        )

        traj_col_national, bullet_col_national = st.columns(2)
        with traj_col_national:
            st.plotly_chart(build_trajectoire(pd.DataFrame(national_ops), montant_programme_national), use_container_width=True)
        with bullet_col_national:
            if not df_fonds_pilotage_national.empty:
                st.plotly_chart(
                    build_ranking_programme_vs_engage(df_fonds_pilotage_national, "fonds", "engage", "programme", height=400),
                    use_container_width=True,
                )
    else:
        st.info("Pas de donnée programmée (Tableau 9B) pour le Volet national avec les fonds sélectionnés.")

    render_region_gestion(df_national_analysis_ops, "le Volet national")

    st.caption(
        "Fonction comptable (certification) : depuis 2021-2027, cette fonction est intégrée à "
        "l'Autorité de gestion (règlement (UE) 2021/1060, art. 76) — il n'y a plus d'autorité de "
        "certification distincte comme sur 2014-2020, donc pas d'espace séparé pour elle ici."
    )

with tab_audit:
    render_region_audit(df_national_analysis_ops, "le Volet national", key_suffix="_volet_national")
