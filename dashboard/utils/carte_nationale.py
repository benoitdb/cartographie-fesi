"""Carte nationale : la métropole et les six DROM-COM sur une échelle de couleur commune.

Écrite trois fois avant l'issue #157 (écart D1) : Accueil, et deux fois la page 2014-2020
(Ensemble national, ventilation régionale du PON FSE). Chaque appelant garde ce qui lui
est propre — l'échelle de couleur, qu'il calcule sur les montants qu'il juge comparables,
et, pour l'Ensemble national 2014-2020, la trace grise des régions hors Synergie.

Échelle commune : si chaque vignette DROM-COM se colorait sur son seul montant, un petit
territoire ressortirait aussi foncé qu'une grande région bien plus dotée.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.data_loader import load_dromcom_geojson
from utils.plot_style import (
    MAP_CONFIG,
    build_standalone_colorbar,
    disable_map_interaction,
    style_hover,
    style_map_background,
)

DROM_COM = ["Guadeloupe", "Martinique", "Guyane", "La Réunion", "Mayotte", "Saint-Martin"]


def _mettre_en_forme(fig, height):
    fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=height, coloraxis_showscale=False)
    return disable_map_interaction(style_map_background(style_hover(fig)))


def render_carte_nationale(
    by_region,
    geojson,
    color_range,
    libelle_montant="Montant UE",
    regions_exclues=(),
    trace_supplementaire=None,
    legendes_metropole=(),
):
    """Légende, carte de la métropole et grille 2×3 des DROM-COM, côte à côte.

    by_region : {région: {"montant_ue_total", "count"}}. libelle_montant : libellé du
    montant au survol (« Montant UE programmé » en 2014-2020, #83) ; la légende garde
    « Montant UE (€) », un titre plus long y étant tronqué.

    regions_exclues / trace_supplementaire : régions retirées de la trace bleue et
    remplacées par une trace à part, sur sa propre échelle (page 2014-2020 : régions hors
    Synergie en gris, #68, #110). legendes_metropole : légendes affichées sous la carte."""
    col_legend, col_metro, col_dromcom = st.columns([1, 4, 6])

    with col_legend:
        st.plotly_chart(
            build_standalone_colorbar(color_range, "Montant UE (€)", height=480),
            width='stretch',
            config={"displayModeBar": False},
        )

    with col_metro:
        st.markdown("**France métropolitaine**")
        regions_metro = {f["properties"]["nom"] for f in geojson["features"]}
        df_carte = pd.DataFrame(
            [
                {"region": region, "montant_ue_total": v["montant_ue_total"], "count": v["count"]}
                for region, v in by_region.items()
                if region in regions_metro and region not in regions_exclues
            ]
        )
        if not df_carte.empty:
            fig = px.choropleth(
                df_carte,
                geojson=geojson,
                locations="region",
                featureidkey="properties.nom",
                color="montant_ue_total",
                color_continuous_scale="Blues",
                range_color=color_range,
                custom_data=["count"],
                labels={"montant_ue_total": f"{libelle_montant} (€)"},
            )
            fig.update_traces(
                hovertemplate=f"<b>%{{location}}</b><br>{libelle_montant} : %{{z:,.0f}} €<br>Nb projets : %{{customdata[0]}}<extra></extra>"
            )
            if trace_supplementaire is not None:
                # Ajoutée avant la mise en forme, pour en recevoir le même survol et le même fond.
                fig.add_trace(trace_supplementaire)
            st.plotly_chart(_mettre_en_forme(fig, height=480), width='stretch', config=MAP_CONFIG)
        for legende in legendes_metropole:
            st.caption(legende)

    with col_dromcom:
        st.markdown("**DROM-COM**")
        dromcom_geojson = load_dromcom_geojson()
        dromcom_rows = st.columns(3), st.columns(3)
        # strict=True : les 2x3 colonnes doivent couvrir exactement DROM_COM — ajouter un
        # territoire sans ajouter la colonne le ferait disparaître de la page en silence.
        for territoire, col in zip(DROM_COM, dromcom_rows[0] + dromcom_rows[1], strict=True):
            valeurs = by_region.get(territoire, {"montant_ue_total": 0, "count": 0})
            with col, st.container(border=True):
                st.markdown(f"**{territoire}**")
                fig_dromcom = px.choropleth(
                    pd.DataFrame([{"region": territoire, "montant_ue_total": valeurs["montant_ue_total"]}]),
                    geojson=dromcom_geojson,
                    locations="region",
                    featureidkey="properties.nom",
                    color="montant_ue_total",
                    color_continuous_scale="Blues",
                    range_color=color_range,
                )
                fig_dromcom.update_traces(
                    hovertemplate=f"<b>{territoire}</b><br>{libelle_montant} : %{{z:,.0f}} €<extra></extra>"
                )
                st.plotly_chart(_mettre_en_forme(fig_dromcom, height=135), width='stretch', config=MAP_CONFIG)
                if valeurs["count"]:
                    montant = f"{valeurs['montant_ue_total'] / 1e6:,.1f} M€".replace(",", " ")
                    st.caption(f"{montant} · {valeurs['count']} projets")
                else:
                    st.caption("Aucun projet")
