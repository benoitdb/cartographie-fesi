import pandas as pd
import plotly.express as px
import streamlit as st

from utils.data_loader import load_data, load_geojson, load_region_metadata
from utils.filters import FONDS_OPTIONS, compute_by_region, render_fonds_filter, summarize_ops
from utils.stats import (
    build_boxplot,
    build_cumulative_curve,
    build_histogram,
    build_portfolio_scatter,
    compute_cofinancement_table,
    compute_stats_table,
    compute_top_beneficiaires,
    detect_cofinancement_outliers,
    detect_incoherent_cofinancement,
    detect_outliers,
    detect_regroupements_beneficiaire,
)
from utils.plot_style import style_hover, style_map_background
from utils.themes import OBJECTIF_STRATEGIQUE_COLORS
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
        custom_data=["count"],
        labels={"montant_ue_total": "Montant UE (€)"},
    )
    fig.update_traces(
        hovertemplate="<b>%{location}</b><br>Montant UE : %{z:,.0f} €<br>Nb projets : %{customdata[0]}<extra></extra>"
    )
    fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
    fig = style_map_background(style_hover(fig))

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

# Montant FESI par habitant
st.subheader("Montant FESI par habitant")
st.caption(
    "Rapporte le montant UE engagé à la population de chaque région (source : Wikidata) — "
    "permet de comparer des régions de tailles très différentes sans que le poids "
    "démographique ne domine la lecture."
)

region_metadata = load_region_metadata()
rows_par_habitant = [
    {
        "region": region,
        "montant_par_habitant": values["montant_ue_total"] / region_metadata[region]["population"],
        "montant_ue_total": values["montant_ue_total"],
    }
    for region, values in by_region.items()
    if region in region_metadata and region_metadata[region]["population"]
]
df_par_habitant = pd.DataFrame(rows_par_habitant).sort_values("montant_par_habitant")

fig_par_habitant = px.bar(
    df_par_habitant,
    x="montant_par_habitant",
    y="region",
    orientation="h",
    hover_data=["montant_ue_total"],
    labels={"montant_par_habitant": "Montant UE par habitant (€)", "region": "", "montant_ue_total": "Montant UE total (€)"},
)
fig_par_habitant.update_layout(height=550, showlegend=False)
fig_par_habitant.for_each_trace(
    lambda t: t.update(
        hovertemplate="<b>%{y}</b><br>Montant UE / habitant : %{x:,.0f} €<br>Montant UE total : %{customdata[0]:,.0f} €<extra></extra>"
    )
)
fig_par_habitant = style_hover(fig_par_habitant)

st.plotly_chart(fig_par_habitant, use_container_width=True)

df_national_ops = pd.DataFrame([op for op in data["operations"] if op.get("Fonds") in selected_fonds])
df_national_ops[LEVEL1] = df_national_ops[LEVEL1].fillna("Non spécifié")
df_national_ops[LEVEL2] = df_national_ops[LEVEL2].fillna("Non spécifié")

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
fig_fonds.for_each_trace(
    lambda t: t.update(
        hovertemplate=f"<b>{t.name}</b><br>Montant UE : %{{x:,.0f}} €<br>Nb projets : %{{customdata[0]:,.0f}}<extra></extra>"
    )
)
fig_fonds = style_hover(fig_fonds)

fonds_col, progress_col = st.columns(2)
with fonds_col:
    st.plotly_chart(fig_fonds, use_container_width=True)
with progress_col:
    st.caption(
        "Engagement UE cumulé dans le temps. Basé sur la date de début de l'opération — environ 60% "
        "des dates sont arrondies au 1ᵉʳ janvier (date administrative plutôt qu'une date de démarrage "
        "précise), d'où des paliers plutôt qu'une progression lissée. Cliquer sur un fonds dans la "
        "légende pour l'isoler ou le masquer."
    )
    st.plotly_chart(build_cumulative_curve(df_national_ops), use_container_width=True)

# Fonds, objectifs stratégiques et spécifiques
st.subheader("Fonds, objectifs stratégiques et spécifiques")

fig_hierarchy = build_hierarchy_treemap(df_national_ops, [FONDS, LEVEL1, LEVEL2])

st.plotly_chart(fig_hierarchy, use_container_width=True)

# Analyses statistiques
st.subheader("Analyses statistiques")
st.caption(
    "Ces indicateurs complètent les agrégats de base (somme, moyenne) affichés plus haut : ils "
    "renseignent sur la dispersion des montants, la concentration du portefeuille et la cohérence "
    "des taux de cofinancement — des repères usuels pour l'analyse de dépense publique."
)

st.caption(
    "Distribution des montants UE par opération, à l'échelle nationale. Ces montants sont très "
    "asymétriques (majorité de petites opérations, quelques grands projets) : l'échelle "
    "logarithmique rend la forme de la distribution plus lisible."
)
echelle_hist = st.radio("Échelle", ["Logarithmique", "Linéaire"], horizontal=True, key="echelle_hist_national")
st.plotly_chart(
    build_histogram(df_national_ops, log_x=echelle_hist == "Logarithmique", color_col="Fonds"),
    use_container_width=True,
)

montant_col_config = st.column_config.NumberColumn(format="%d €")
cv_col_config = st.column_config.NumberColumn(
    "Coeff. de variation", help="Écart-type / médiane — dispersion relative, comparable entre groupes de tailles différentes"
)
concentration_col_config = st.column_config.NumberColumn(
    "Concentration (top 10%)", format="percent", help="Part du montant total portée par les 10% de projets les plus importants du groupe"
)
stats_col_config = {
    "Médiane": montant_col_config,
    "Écart-type": montant_col_config,
    "cv": cv_col_config,
    "concentration_top10": concentration_col_config,
}

st.caption(
    "La médiane et l'écart-type mesurent la dispersion des montants au sein d'un groupe. Le "
    "coefficient de variation (écart-type / médiane) rend cette dispersion comparable entre "
    "groupes de tailles très différentes. La concentration indique la part du montant total "
    "portée par les 10% de projets les plus importants du groupe. Chaque boîte à moustaches "
    "représente la médiane et l'écart interquartile (IQR) ; les points au-delà des moustaches "
    "sont les opérations à montant atypique."
)
echelle_box = st.radio("Échelle des boîtes à moustaches", ["Logarithmique", "Linéaire"], horizontal=True, key="echelle_box_national")

mono_region = df_national_ops["regions_modernes"].apply(lambda r: isinstance(r, list) and len(r) == 1)
df_mono_region = df_national_ops[
    mono_region & ~df_national_ops["is_interregional"] & ~df_national_ops["is_national"]
].copy()
df_mono_region["Région"] = df_mono_region["regions_modernes"].apply(lambda r: r[0])

col_fonds, box_col_fonds = st.columns(2)
with col_fonds:
    st.markdown("**Médiane, écart-type et concentration par fonds**")
    stats_fonds = compute_stats_table(df_national_ops, "Fonds").rename(
        columns={"mediane": "Médiane", "ecart_type": "Écart-type", "count": "Nb projets"}
    )
    st.dataframe(stats_fonds, hide_index=True, use_container_width=True, column_config=stats_col_config)
with box_col_fonds:
    st.plotly_chart(
        build_boxplot(df_national_ops, "Fonds", log_y=echelle_box == "Logarithmique"), use_container_width=True
    )

st.markdown("**Distribution par objectif stratégique**")
st.plotly_chart(
    build_boxplot(
        df_national_ops, LEVEL1, log_y=echelle_box == "Logarithmique", color_map=OBJECTIF_STRATEGIQUE_COLORS
    ),
    use_container_width=True,
)

st.markdown("**Médiane, écart-type et concentration par région**")
stats_region = compute_stats_table(df_mono_region, "Région").rename(
    columns={"mediane": "Médiane", "ecart_type": "Écart-type", "count": "Nb projets"}
)
st.dataframe(stats_region, hide_index=True, use_container_width=True, column_config=stats_col_config)

st.plotly_chart(
    build_boxplot(df_mono_region, "Région", log_y=echelle_box == "Logarithmique"), use_container_width=True
)

st.markdown("**Opérations à montant atypique**")
st.caption(
    "Opérations dont le montant s'écarte fortement de la distribution habituelle du groupe "
    "(méthode IQR) — à examiner, sans présumer d'une anomalie : un montant élevé peut aussi "
    "correspondre à un projet structurant légitime."
)
outliers = detect_outliers(df_national_ops)
st.caption(f"{len(outliers)} opération(s) hors de l'intervalle interquartile habituel.")
st.dataframe(
    outliers[["Intitulé du projet", "Nom du bénéficiaire", "Fonds", "Région de l'opération", "Montant UE"]].head(50),
    hide_index=True,
    use_container_width=True,
    column_config={"Montant UE": montant_col_config},
)

st.markdown("**Concentration par bénéficiaire**")
st.caption(
    "Bénéficiaires cumulant le plus de montant UE, tous projets confondus — vue d'ensemble des "
    "acteurs les plus représentés dans le portefeuille."
)
top_beneficiaires = compute_top_beneficiaires(df_national_ops).rename(
    columns={"montant_ue_total": "Montant UE cumulé", "count": "Nb projets"}
)
st.dataframe(
    top_beneficiaires,
    hide_index=True,
    use_container_width=True,
    column_config={"Montant UE cumulé": montant_col_config},
)

st.markdown("**Opérations rapprochées par bénéficiaire**")
st.caption(
    "On regarde ici de près les opérations d'un même bénéficiaire dont le montant et la date de "
    "démarrage sont proches."
)
proches, grands_regroupements = detect_regroupements_beneficiaire(df_national_ops)

st.caption(
    f"Petits regroupements (2 à 3 opérations) : {len(proches)} bénéficiaire(s). Les programmes "
    "découpés en lots (nombreuses opérations très proches par construction) peuvent malgré tout "
    "apparaître si le nombre de lots reste faible."
)
if len(proches):
    st.dataframe(
        proches.head(50),
        hide_index=True,
        use_container_width=True,
        column_config={"Montant UE cumulé": montant_col_config},
    )

st.caption(
    f"Grands regroupements (4 opérations ou plus) : {len(grands_regroupements)} bénéficiaire(s). Le "
    "coefficient de variation indique la dispersion des montants au sein du regroupement (proche de "
    "0 : montants quasi identiques ; élevé : montants très inégaux, ex. plusieurs lots de tailles "
    "différentes)."
)
if len(grands_regroupements):
    st.dataframe(
        grands_regroupements.head(50),
        hide_index=True,
        use_container_width=True,
        column_config={
            "Montant UE cumulé": montant_col_config,
            "Coeff. de variation": st.column_config.NumberColumn(format="%.2f"),
        },
    )

st.markdown("**Structure du portefeuille par région**")
st.caption(
    "Nombre de projets (x) vs montant UE moyen (y), taille de bulle = montant UE total : distingue "
    "les régions portées par peu de gros projets de celles portées par de nombreux petits projets."
)
st.plotly_chart(build_portfolio_scatter(df_mono_region, "Région"), use_container_width=True)

st.markdown("**Taux de cofinancement UE**")
st.caption(
    "Le taux de cofinancement est plafonné réglementairement selon le fonds et la catégorie de région "
    "(plafonds non modélisés ici) ; un taux atypique peut signaler une opération à vérifier."
)
taux_col_config = st.column_config.NumberColumn(format="percent")
cofinancement_fonds = compute_cofinancement_table(df_national_ops, "Fonds").rename(
    columns={"taux_moyen": "Taux moyen", "taux_median": "Taux médian", "count": "Nb projets"}
)
st.dataframe(
    cofinancement_fonds,
    hide_index=True,
    use_container_width=True,
    column_config={"Taux moyen": taux_col_config, "Taux médian": taux_col_config},
)

cofinancement_outliers = detect_cofinancement_outliers(df_national_ops).assign(
    **{"Montant hors UE": lambda d: d["Total des dépenses éligibles"] - d["Montant UE"]}
)
st.caption(f"{len(cofinancement_outliers)} opération(s) à taux de cofinancement atypique (méthode IQR).")
st.dataframe(
    cofinancement_outliers[
        [
            "Intitulé du projet",
            "Nom du bénéficiaire",
            "Fonds",
            "Région de l'opération",
            "Total des dépenses éligibles",
            "Montant UE",
            "Montant hors UE",
            "Taux de cofinancement",
        ]
    ].head(50),
    hide_index=True,
    use_container_width=True,
    column_config={
        "Taux de cofinancement": taux_col_config,
        "Total des dépenses éligibles": montant_col_config,
        "Montant UE": montant_col_config,
        "Montant hors UE": montant_col_config,
    },
)

st.markdown("**Cohérence des montants**")
st.caption(
    "Contrôle de cohérence (pas une question de distribution) : opérations où le montant UE "
    "dépasse le total des dépenses éligibles, ce qui correspondrait à un taux de cofinancement "
    "supérieur à 100%, normalement impossible — à vérifier, potentiel signal de qualité de données."
)
incoherentes = detect_incoherent_cofinancement(df_national_ops)
st.caption(f"{len(incoherentes)} opération(s) où le montant UE dépasse le total des dépenses éligibles.")
if len(incoherentes):
    st.dataframe(
        incoherentes[
            ["Intitulé du projet", "Nom du bénéficiaire", "Fonds", "Total des dépenses éligibles", "Montant UE", "Taux de cofinancement"]
        ].head(50),
        hide_index=True,
        use_container_width=True,
        column_config={
            "Total des dépenses éligibles": montant_col_config,
            "Montant UE": montant_col_config,
            "Taux de cofinancement": taux_col_config,
        },
    )

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
    fig_national_fonds.for_each_trace(
        lambda t: t.update(
            hovertemplate=f"<b>{t.name}</b><br>Montant UE : %{{x:,.0f}} €<br>Nb projets : %{{customdata[0]:,.0f}}<extra></extra>"
        )
    )
    fig_national_fonds = style_hover(fig_national_fonds)

    st.plotly_chart(fig_national_fonds, use_container_width=True)

    # Courbe cumulée d'engagement UE dans le temps (Volet national)
    st.subheader("Engagement UE cumulé dans le temps")
    st.caption(
        "Basé sur la date de début de l'opération. Environ 60% des dates sont arrondies au 1ᵉʳ janvier "
        "(date administrative/programmatique plutôt qu'une date de démarrage individuelle précise) : "
        "la courbe présente donc des paliers plutôt qu'une progression lissée."
    )
    st.caption("Cliquer sur un fonds dans la légende pour l'isoler ou le masquer.")

    st.plotly_chart(build_cumulative_curve(pd.DataFrame(national_ops)), use_container_width=True)
