import pandas as pd
import plotly.express as px
import streamlit as st

from utils.data_loader import (
    load_beneficiaires_fuzzy,
    load_data,
    load_dotations_os,
    load_dromcom_geojson,
    load_geojson,
    load_interreg,
    load_programme_totals,
    load_region_metadata,
    load_transferts_solidarite,
)
from utils.filters import FONDS_OPTIONS, compute_by_region, render_fonds_filter, summarize_ops
from utils.pilotage import RESERVE_METHODO, build_ranking_programme_vs_engage, render_kpi_pilotage
from utils.stats import (
    build_boxplot,
    build_cumulative_curve,
    build_fonds_barchart,
    build_histogram,
    build_lorenz_beneficiaires,
    build_pareto_beneficiaires,
    build_portfolio_scatter,
    compute_cofinancement_table,
    compute_stats_table,
    detect_cofinancement_outliers,
    detect_incoherent_cofinancement,
    detect_beneficiaires_multi_region,
    detect_outliers,
    detect_regroupements_beneficiaire,
    render_top_beneficiaires_drilldown,
)
from utils.plot_style import MAP_CONFIG, build_standalone_colorbar, disable_map_interaction, style_hover, style_map_background
from utils.table_style import text_widths
from utils.themes import FONDS_COLORS, OBJECTIF_STRATEGIQUE_COLORS, style_categorical_columns
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
    national_summary = summarize_ops([op for op in ops_selected if op.get("is_national")])
    interregional_summary = summarize_ops([op for op in ops_selected if op.get("is_interregional")])
else:
    # Fonds par défaut (tous sélectionnés) : agrégats pré-calculés du pipeline, comportement inchangé
    by_region = data["aggregates"]["by_region"]
    national_summary = data["aggregates"]["national"]
    interregional_summary = data["aggregates"]["interregional"]

# Bandeau KPI — le total doit couvrir toutes les opérations, pas seulement celles mono-région
# de by_region : le volet national et les opérations interrégionales (montant/nombre de
# projets) en étaient absents jusqu'ici, le total affiché sous-comptait ~700 opérations.
total_montant_regional = sum(v["montant_ue_total"] for v in by_region.values())
total_count_regional = sum(v["count"] for v in by_region.values())
total_montant = total_montant_regional + national_summary["montant_ue_total"] + interregional_summary["montant_ue_total"]
total_count = total_count_regional + national_summary["count"] + interregional_summary["count"]
count_regions = total_count - national_summary["count"]  # projets en région (mono-région + interrégional)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Montant UE total", f"{total_montant / 1e6:,.1f} M€".replace(",", " "))
col2.metric("Nombre de projets", f"{total_count:,}".replace(",", " "))
col3.metric("Régions", f"{count_regions:,}".replace(",", " "))
col4.metric("Volet national", f"{national_summary['count']:,}".replace(",", " "))
if interregional_summary["count"]:
    st.caption(
        f"Dont {interregional_summary['count']} opération(s) interrégionale(s) (plusieurs régions à la "
        "fois), incluses dans le total ci-dessus mais non ventilées par région ni dans le volet national."
    )

DROM_COM = ["Guadeloupe", "Martinique", "Guyane", "La Réunion", "Mayotte", "Saint-Martin"]

# Échelle de couleur partagée entre la carte métropole et les vignettes DROM-COM ci-dessous :
# si chaque vignette se colorait sur sa propre échelle (son seul montant), un petit territoire
# ressortirait aussi "foncé" qu'une grande région bien plus dotée — trompeur. Avec une échelle
# commune, l'intensité de couleur reste comparable sur l'ensemble du territoire national.
montants_nationaux = [values["montant_ue_total"] for region, values in by_region.items() if region in regions_metro or region in DROM_COM]
color_range = [0, max(montants_nationaux)] if montants_nationaux else [0, 1]

st.subheader("Répartition géographique du montant UE")
st.caption(
    "Contour réel de chaque territoire, DROM-COM compris (et non un simple repère), sur une "
    "échelle de couleur commune — malgré la distance et la taille très différentes de ces "
    "territoires, l'intensité de bleu reste directement comparable partout."
)

col_legend, col_metro, col_dromcom = st.columns([1, 4, 6])

with col_legend:
    st.plotly_chart(
        build_standalone_colorbar(color_range, "Montant UE (€)", height=480),
        use_container_width=True,
        config={"displayModeBar": False},
    )

with col_metro:
    st.markdown("**France métropolitaine**")
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
        range_color=color_range,
        custom_data=["count"],
        labels={"montant_ue_total": "Montant UE (€)"},
    )
    fig.update_traces(
        hovertemplate="<b>%{location}</b><br>Montant UE : %{z:,.0f} €<br>Nb projets : %{customdata[0]}<extra></extra>"
    )
    fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=480, coloraxis_showscale=False)
    fig = disable_map_interaction(style_map_background(style_hover(fig)))

    st.plotly_chart(fig, use_container_width=True, config=MAP_CONFIG)

with col_dromcom:
    st.markdown("**DROM-COM**")
    dromcom_geojson = load_dromcom_geojson()

    dromcom_rows = st.columns(3), st.columns(3)
    for territory, col in zip(DROM_COM, dromcom_rows[0] + dromcom_rows[1]):
        values = by_region.get(territory, {"montant_ue_total": 0, "count": 0})
        with col:
            with st.container(border=True):
                st.markdown(f"**{territory}**")
                fig_dromcom = px.choropleth(
                    pd.DataFrame([{"region": territory, "montant_ue_total": values["montant_ue_total"]}]),
                    geojson=dromcom_geojson,
                    locations="region",
                    featureidkey="properties.nom",
                    color="montant_ue_total",
                    color_continuous_scale="Blues",
                    range_color=color_range,
                )
                fig_dromcom.update_traces(hovertemplate=f"<b>{territory}</b><br>Montant UE : %{{z:,.0f}} €<extra></extra>")
                fig_dromcom.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
                fig_dromcom.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=135, coloraxis_showscale=False)
                fig_dromcom = disable_map_interaction(style_map_background(style_hover(fig_dromcom)))
                st.plotly_chart(fig_dromcom, use_container_width=True, config=MAP_CONFIG)
                if values["count"]:
                    st.caption(f"{values['montant_ue_total'] / 1e6:,.1f} M€ · {values['count']} projets".replace(",", " "))
                else:
                    st.caption("Aucun projet")

df_national_ops = pd.DataFrame([op for op in data["operations"] if op.get("Fonds") in selected_fonds])
df_national_ops[LEVEL1] = df_national_ops[LEVEL1].fillna("Non spécifié")
df_national_ops[LEVEL2] = df_national_ops[LEVEL2].fillna("Non spécifié")

mono_region = df_national_ops["regions_modernes"].apply(lambda r: isinstance(r, list) and len(r) == 1)
df_mono_region = df_national_ops[
    mono_region & ~df_national_ops["is_interregional"] & ~df_national_ops["is_national"]
].copy()
df_mono_region["Région"] = df_mono_region["regions_modernes"].apply(lambda r: r[0])

montant_col_config = st.column_config.NumberColumn(format="%,d €")
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
taux_col_config = st.column_config.NumberColumn(format="percent")

tab_ensemble, tab_pilotage, tab_audit = st.tabs(["Vue d'ensemble", "Pilotage", "Analyses & contrôle"])

with tab_ensemble:
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

    # Repère programmé (Tableau 9B) par fonds, à l'échelle nationale : somme de toutes les
    # enveloppes régionales + la clé "national" (volet national) de programme_totals.json —
    # même source que le pilotage programmé vs engagé par région, agrégée ici au niveau pays.
    totaux_programme_national = {}
    for perimetre_totals in load_programme_totals().values():
        for f, v in perimetre_totals.items():
            if f in selected_fonds:
                totaux_programme_national[f] = totaux_programme_national.get(f, 0) + v

    # Même échelle verticale sur les deux graphes (barres et courbe cumulée) : sans ça, le repère
    # pointillé programmé (souvent au-dessus du montant engagé) étire l'axe de la courbe au-delà
    # de celui des barres, et les deux graphes cessent de se lire à la même hauteur.
    montant_max_fonds = max(
        df_fonds["montant_ue_total"].max(),
        max(totaux_programme_national.values(), default=0),
    )
    axe_range = [0, montant_max_fonds * 1.05]

    # Barres verticales (plutôt qu'horizontales) pour une hauteur cohérente avec la courbe
    # cumulée affichée à côté — les deux graphes se lisent alors sur le même axe vertical
    # (montant), la courbe cumulée étant elle-même naturellement "en hauteur". Empilée avec un
    # segment "Reste à engager" (totaux_programme_national) : le sommet de chaque barre
    # rejoint l'enveloppe programmée, comme le repère pointillé de la courbe cumulée mais
    # visible directement sur les barres (issue #33bis).
    fig_fonds = build_fonds_barchart(df_fonds, FONDS_COLORS, totaux_programme=totaux_programme_national)
    fig_fonds.update_layout(height=450)
    fig_fonds.update_yaxes(range=axe_range)

    mode_courbe = st.radio("Courbe cumulée", ["Montant", "%"], horizontal=True, key="mode_courbe_national")
    mode_courbe_val = "pourcentage" if mode_courbe == "%" else "montant"

    fig_cumulative = build_cumulative_curve(
        df_national_ops, color_map=FONDS_COLORS, totaux_ref=totaux_programme_national, mode=mode_courbe_val
    )
    if mode_courbe_val == "montant":
        fig_cumulative.update_yaxes(range=axe_range)

    st.caption(
        "Engagement UE cumulé dans le temps. Basé sur la date de début de l'opération — environ 60% des "
        "dates sont arrondies au 1ᵉʳ janvier (date administrative plutôt qu'une date de démarrage précise), "
        "d'où des paliers plutôt qu'une progression lissée. Cliquer sur un fonds dans la légende pour "
        "l'isoler ou le masquer. Repère pointillé : enveloppe programmée nationale par fonds (Tableau 9B, "
        "toutes régions et volet national confondus) — en mode %, repère unique à 100%. " + RESERVE_METHODO
    )
    fonds_col, progress_col = st.columns([3, 7])
    with fonds_col:
        st.plotly_chart(fig_fonds, use_container_width=True)
    with progress_col:
        st.plotly_chart(fig_cumulative, use_container_width=True)

    # Fonds, objectifs stratégiques et spécifiques
    st.subheader("Fonds, objectifs stratégiques et spécifiques")

    fig_hierarchy = build_hierarchy_treemap(df_national_ops, [FONDS, LEVEL1, LEVEL2])

    st.plotly_chart(fig_hierarchy, use_container_width=True)

    st.markdown("**Structure du portefeuille par région**")
    st.caption(
        "Nombre de projets (x) vs montant UE moyen (y), taille de bulle = montant UE total : distingue "
        "les régions portées par peu de gros projets de celles portées par de nombreux petits projets."
    )
    st.plotly_chart(build_portfolio_scatter(df_mono_region, "Région"), use_container_width=True)

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
        st.caption("Opérations non rattachées à une région (ex. programmes nationaux France Travail pour l'emploi).")
        st.page_link("pages/2_Volet_National.py", label="Voir l'analyse complète du Volet national", icon="➡️")

    # Programmes Interreg — liste de référence uniquement (issue #19) : aucune opération Interreg
    # dans data.json (vérifié : les codes CCI présents suivent tous la série "2021FR...", série
    # distincte des codes Interreg "2021TC..." ci-dessous — absence structurelle des données, pas
    # un défaut d'étiquetage), et le Tableau 10 source ne donne aucun montant. Pas de KPI ni de
    # graphe ici, volontairement : rien à mesurer, seulement à recenser.
    st.subheader("Programmes Interreg (coopération territoriale européenne)")
    st.caption(
        "La France participe à 18 programmes Interreg 2021-2027, pilotés par une autorité de "
        "gestion transnationale (pas par la France seule) — aucune opération ni montant "
        "disponible dans les données de ce dashboard, seulement la liste des programmes "
        "(Accord de partenariat, Tableau 10)."
    )
    interreg_programmes = load_interreg()
    df_interreg = pd.DataFrame(interreg_programmes).rename(
        columns={"cci": "Code CCI", "intitule": "Programme", "type": "Type"}
    )
    df_interreg["Type"] = df_interreg["Type"].map(
        {"VI-A": "VI-A · Transfrontalier", "VI-B": "VI-B · Transnational", "VI-D": "VI-D · Régions ultrapériphériques"}
    )
    st.dataframe(
        df_interreg[["Programme", "Type", "Code CCI"]].sort_values(["Type", "Programme"]),
        hide_index=True,
        use_container_width=True,
        column_config=text_widths("Programme", "Type", "Code CCI"),
    )

with tab_pilotage:
    # Pilotage par Objectif Stratégique (national uniquement — voir issue #21/#28 : le Tableau 8 de
    # l'Accord de partenariat ne ventile pas les dotations par région nommée, contrairement au
    # Tableau 9B utilisé pour le pilotage par Fonds plus bas).
    st.subheader("Pilotage par Objectif Stratégique (national)")
    dotations_os = load_dotations_os()
    engage_par_os = df_national_ops.groupby(LEVEL1)["Montant UE"].sum()
    rows_os_pilotage = [
        {
            "fonds": os,
            "programme": sum(v for f, v in fonds_montants.items() if f in selected_fonds),
            "engage": engage_par_os.get(os, 0),
        }
        for os, fonds_montants in dotations_os.items()
    ]
    df_os_pilotage = pd.DataFrame(rows_os_pilotage, columns=["fonds", "programme", "engage"])
    df_os_pilotage = df_os_pilotage[df_os_pilotage["programme"] > 0]
    render_kpi_pilotage(df_os_pilotage, df_os_pilotage["programme"].sum(), df_os_pilotage["engage"].sum(), color_map=OBJECTIF_STRATEGIQUE_COLORS)

    # Comparaison régionale — montant par habitant et taux de consommation mesurent deux choses
    # différentes mais prennent tous les deux la forme d'un classement de régions ; les afficher
    # l'un sous l'autre créait une impression de redondance (issue #26). Un seul à la fois via ce
    # bouton radio, rien de supprimé : les deux calculs restent complets, seul un est exécuté par
    # rerun (l'autre branche n'est simplement pas prise).
    st.subheader("Comparaison régionale")

    with st.expander("ℹ️ Pourquoi les dotations diffèrent-elles entre catégories de région ?"):
        st.caption(
            "Au nom du principe de solidarité entre régions, une partie de la dotation initiale "
            "des catégories \"Plus développées\" et \"En transition\" est reversée à la catégorie "
            "\"Moins développées\" sur 2022-2027 (Accord de partenariat, Tableau 3A/3B). Ce "
            "mécanisme est national et global — il n'est pas ventilé par région ni par opération, "
            "donc non croisable avec les données ci-dessous, mais il explique en partie pourquoi "
            "les enveloppes programmées (Tableau 9B, utilisées pour le taux de consommation) "
            "dépassent la dotation initiale d'une région \"moins développée\"."
        )
        transferts_solidarite = load_transferts_solidarite()
        df_transferts = pd.DataFrame(
            [
                {
                    "Catégorie d'origine": t["categorie_origine"],
                    "Montant transféré (2022-2027)": t["total_publie"],
                    "Part de la dotation initiale": t["part_dotation_transferee"] * 100,
                }
                for t in transferts_solidarite["transferts"]
            ]
        )
        st.dataframe(
            df_transferts,
            hide_index=True,
            use_container_width=True,
            column_config={
                **text_widths("Catégorie d'origine"),
                "Montant transféré (2022-2027)": st.column_config.NumberColumn(format="%d €"),
                "Part de la dotation initiale": st.column_config.NumberColumn(format="%.0f%%"),
            },
        )
        st.caption("Transferts vers la catégorie \"Moins développées\", seule catégorie destinataire.")

    choix_comparaison = st.radio(
        "Indicateur",
        ["Montant par habitant", "Taux de consommation"],
        horizontal=True,
        key="choix_comparaison_regionale",
    )

    if choix_comparaison == "Montant par habitant":
        st.caption(
            "Rapporte le montant UE engagé à la population de chaque région (source : Wikidata), "
            "décomposé par fonds — permet de comparer des régions de tailles très différentes sans "
            "que le poids démographique ne domine la lecture, et de voir quel fonds pèse le plus "
            "dans chaque région."
        )

        region_metadata = load_region_metadata()
        ops_par_habitant = [
            op
            for op in data["operations"]
            if op.get("Fonds") in selected_fonds
            and isinstance(op.get("regions_modernes"), list)
            and len(op["regions_modernes"]) == 1
            and not op.get("is_interregional")
            and not op.get("is_national")
        ]
        df_ops_par_habitant = pd.DataFrame(ops_par_habitant)
        df_ops_par_habitant["region"] = df_ops_par_habitant["regions_modernes"].apply(lambda r: r[0])

        df_par_habitant = (
            df_ops_par_habitant.groupby(["region", "Fonds"])["Montant UE"]
            .sum()
            .reset_index()
            .rename(columns={"Montant UE": "montant_ue_total"})
        )
        df_par_habitant = df_par_habitant[
            df_par_habitant["region"].map(lambda r: bool(region_metadata.get(r, {}).get("population")))
        ]
        df_par_habitant["population"] = df_par_habitant["region"].map(lambda r: region_metadata[r]["population"])
        df_par_habitant["montant_par_habitant"] = df_par_habitant["montant_ue_total"] / df_par_habitant["population"]

        total_par_habitant_par_region = df_par_habitant.groupby("region")["montant_par_habitant"].sum()
        df_par_habitant["total_region_par_habitant"] = df_par_habitant["region"].map(total_par_habitant_par_region)
        region_order = total_par_habitant_par_region.sort_values().index.tolist()

        fig_par_habitant = px.bar(
            df_par_habitant,
            x="montant_par_habitant",
            y="region",
            color="Fonds",
            color_discrete_map=FONDS_COLORS,
            orientation="h",
            category_orders={"region": region_order},
            hover_data=["montant_ue_total", "total_region_par_habitant"],
            labels={"montant_par_habitant": "Montant UE par habitant (€)", "region": "", "montant_ue_total": "Montant UE total (€)", "Fonds": "Fonds"},
        )
        fig_par_habitant.update_layout(height=550, barmode="stack")
        fig_par_habitant.for_each_trace(
            lambda t: t.update(
                hovertemplate=(
                    f"<b>%{{y}}</b><br>{t.name} : %{{x:,.0f}} €/hab. (%{{customdata[0]:,.0f}} € au total)"
                    "<br>Total FESI : %{customdata[1]:,.0f} €/hab.<extra></extra>"
                )
            )
        )
        fig_par_habitant = style_hover(fig_par_habitant)

        st.plotly_chart(fig_par_habitant, use_container_width=True)
    else:
        st.caption(
            "Montant engagé rapporté à l'enveloppe programmée 2021-2027 (Accord de partenariat, "
            "Tableau 9B, tous fonds sélectionnés confondus). " + RESERVE_METHODO
        )

        programme_totals = load_programme_totals()
        rows_consommation = [
            {
                "region": region,
                "engage": values["montant_ue_total"],
                "programme": sum(v for f, v in programme_totals[region].items() if f in selected_fonds),
            }
            for region, values in by_region.items()
            if region in programme_totals
        ]
        df_consommation = pd.DataFrame(rows_consommation)
        df_consommation = df_consommation[df_consommation["programme"] > 0]

        fig_consommation = build_ranking_programme_vs_engage(df_consommation, "region", "engage", "programme")

        st.plotly_chart(fig_consommation, use_container_width=True)

    st.caption(
        "Fonction comptable (certification) : depuis 2021-2027, cette fonction est intégrée à "
        "l'Autorité de gestion (règlement (UE) 2021/1060, art. 76) — il n'y a plus d'autorité de "
        "certification distincte comme sur 2014-2020, donc pas d'espace séparé pour elle ici."
    )

with tab_audit:
    st.caption(
        "Ces indicateurs complètent les agrégats de base (somme, moyenne) affichés dans la vue "
        "d'ensemble : ils renseignent sur la dispersion des montants, la concentration du "
        "portefeuille et la cohérence des taux de cofinancement — des repères usuels pour l'analyse "
        "de dépense publique."
    )

    st.caption(
        "Distribution des montants UE par opération, à l'échelle nationale. Ces montants sont très "
        "asymétriques (majorité de petites opérations, quelques grands projets) : l'échelle "
        "logarithmique rend la forme de la distribution plus lisible."
    )
    echelle_hist = st.radio("Échelle", ["Logarithmique", "Linéaire"], horizontal=True, key="echelle_hist_national")
    st.plotly_chart(
        build_histogram(df_national_ops, log_x=echelle_hist == "Logarithmique", color_col="Fonds", color_map=FONDS_COLORS),
        use_container_width=True,
    )

    st.caption(
        "La médiane et l'écart-type mesurent la dispersion des montants au sein d'un groupe. Le "
        "coefficient de variation (écart-type / médiane) rend cette dispersion comparable entre "
        "groupes de tailles très différentes. La concentration indique la part du montant total "
        "portée par les 10% de projets les plus importants du groupe. Chaque boîte à moustaches "
        "représente la médiane et l'écart interquartile (IQR) ; les points au-delà des moustaches "
        "sont les opérations à montant atypique."
    )
    echelle_box = st.radio("Échelle des boîtes à moustaches", ["Logarithmique", "Linéaire"], horizontal=True, key="echelle_box_national")

    col_fonds, box_col_fonds = st.columns(2)
    with col_fonds:
        st.markdown("**Médiane, écart-type et concentration par fonds**")
        stats_fonds = compute_stats_table(df_national_ops, "Fonds").rename(
            columns={"mediane": "Médiane", "ecart_type": "Écart-type", "count": "Nb projets"}
        )
        st.dataframe(
            style_categorical_columns(stats_fonds, {"Fonds": FONDS_COLORS}),
            hide_index=True,
            use_container_width=True,
            column_config={
                **stats_col_config,
                "Médiane": st.column_config.ProgressColumn(format="%,d €", min_value=0, max_value=int(stats_fonds["Médiane"].max())),
            },
        )
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
    st.dataframe(
        stats_region, hide_index=True, use_container_width=True, column_config={**stats_col_config, **text_widths("Région")}
    )

    st.plotly_chart(
        build_boxplot(df_mono_region, "Région", log_y=echelle_box == "Logarithmique"), use_container_width=True
    )

    st.markdown("**Opérations à montant atypique**")
    st.caption(
        "Opérations dont le montant s'écarte fortement de la distribution habituelle de son fonds "
        "(méthode IQR, calculée séparément par Fonds — FEDER, FSE+ et FTJ n'ont pas la même échelle "
        "de montants) — à examiner, sans présumer d'une anomalie : un montant élevé peut aussi "
        "correspondre à un projet structurant légitime."
    )
    outliers = detect_outliers(df_national_ops, group_col="Fonds")
    st.caption(f"{len(outliers)} opération(s) hors de l'intervalle interquartile habituel.")
    outliers_table = outliers[["Intitulé du projet", "Nom du bénéficiaire", "Fonds", "Région de l'opération", "Montant UE"]].head(50)
    st.dataframe(
        style_categorical_columns(outliers_table, {"Fonds": FONDS_COLORS}),
        hide_index=True,
        use_container_width=True,
        column_config={
            **text_widths("Intitulé du projet", "Nom du bénéficiaire", "Région de l'opération"),
            "Montant UE": st.column_config.ProgressColumn(
                format="%,d €", min_value=0, max_value=int(outliers_table["Montant UE"].max()) if len(outliers_table) else 1
            ),
        },
    )

    st.markdown("**Concentration par bénéficiaire**")
    st.caption(
        "Bénéficiaires cumulant le plus de montant UE, tous projets confondus — vue d'ensemble des "
        "acteurs les plus représentés dans le portefeuille."
    )
    st.plotly_chart(build_pareto_beneficiaires(df_national_ops), use_container_width=True)
    with st.expander("Courbe de Lorenz (détail statistique de la concentration)"):
        st.caption(
            "Autre lecture de la même concentration : % cumulé de bénéficiaires (du plus petit au "
            "plus gros) vs % cumulé du montant — plus la courbe s'éloigne de la diagonale "
            "(égalité parfaite), plus le montant est concentré sur peu de bénéficiaires."
        )
        st.plotly_chart(build_lorenz_beneficiaires(df_national_ops), use_container_width=True)

    render_top_beneficiaires_drilldown(df_national_ops, montant_col_config, key="top_beneficiaires_national")

    st.markdown("**Opérations rapprochées par bénéficiaire**")
    st.caption(
        "On regarde ici de près les opérations d'un même bénéficiaire dont le montant et la date de "
        "démarrage sont proches."
    )
    proches, grands_regroupements, regroupements_inter_fonds = detect_regroupements_beneficiaire(df_national_ops)

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
            column_config={**text_widths("Nom du bénéficiaire", "Opérations", "Programme(s)"), "Montant UE cumulé": montant_col_config},
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
                **text_widths("Nom du bénéficiaire"),
                "Montant UE cumulé": montant_col_config,
                "Coeff. de variation": st.column_config.NumberColumn(format="%.2f"),
            },
        )

    st.markdown("**Regroupements inter-fonds**")
    st.caption(
        f"{len(regroupements_inter_fonds)} bénéficiaire(s) avec des opérations rapprochées (montant et "
        "date proches) couvrant plus d'un Fonds (ex. FEDER + FSE+) — signal plus fort qu'un regroupement "
        "intra-programme (lots d'un même accord-cadre, cas le plus fréquent ci-dessus), à recouper, pas "
        "une preuve en soi."
    )
    if len(regroupements_inter_fonds):
        st.dataframe(
            regroupements_inter_fonds,
            hide_index=True,
            use_container_width=True,
            column_config={**text_widths("Nom du bénéficiaire", "Programme(s)", "Opérations"), "Montant UE cumulé": montant_col_config},
        )
    else:
        st.caption("Aucun cas détecté sur le périmètre actuel.")

    st.markdown("**Bénéficiaires présents dans plusieurs régions**")
    st.caption(
        "Un même bénéficiaire (ou une variante proche de saisie du même nom) apparaissant dans "
        "plusieurs régions à la fois — à recouper, pas une preuve en soi : peut correspondre à "
        "une organisation multi-sites tout à fait légitime comme à une saisie à vérifier."
    )
    beneficiaires_fuzzy = load_beneficiaires_fuzzy()
    multi_region = detect_beneficiaires_multi_region(df_national_ops, beneficiaires_fuzzy)
    if len(multi_region):
        multi_region_table = multi_region.head(50)
        st.dataframe(
            multi_region_table,
            hide_index=True,
            use_container_width=True,
            column_config={
                **text_widths("Nom du bénéficiaire", "Régions"),
                "Montant UE cumulé": st.column_config.ProgressColumn(
                    format="%,d €",
                    min_value=0,
                    max_value=int(multi_region_table["Montant UE cumulé"].max()) if len(multi_region_table) else 1,
                ),
            },
        )
    else:
        st.caption("Aucun cas détecté sur le périmètre actuel.")

    st.markdown("**Taux de cofinancement UE**")
    st.caption(
        "Le taux de cofinancement est plafonné réglementairement selon le fonds et la catégorie de région "
        "(plafonds non modélisés ici) ; un taux atypique peut signaler une opération à vérifier."
    )
    cofinancement_fonds = compute_cofinancement_table(df_national_ops, "Fonds").rename(
        columns={"taux_moyen": "Taux moyen", "taux_median": "Taux médian", "count": "Nb projets"}
    )
    st.dataframe(
        style_categorical_columns(cofinancement_fonds, {"Fonds": FONDS_COLORS}),
        hide_index=True,
        use_container_width=True,
        column_config={
            "Taux moyen": st.column_config.ProgressColumn(
                format="percent", min_value=0, max_value=max(1.0, cofinancement_fonds["Taux moyen"].max())
            ),
            "Taux médian": taux_col_config,
        },
    )

    cofinancement_outliers = detect_cofinancement_outliers(df_national_ops).assign(
        **{"Montant hors UE": lambda d: d["Total des dépenses éligibles"] - d["Montant UE"]}
    )
    st.caption(f"{len(cofinancement_outliers)} opération(s) à taux de cofinancement atypique (méthode IQR).")
    cofinancement_outliers_table = cofinancement_outliers[
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
    ].head(50)
    st.dataframe(
        style_categorical_columns(cofinancement_outliers_table, {"Fonds": FONDS_COLORS}),
        hide_index=True,
        use_container_width=True,
        column_config={
            **text_widths("Intitulé du projet", "Nom du bénéficiaire", "Région de l'opération"),
            "Taux de cofinancement": taux_col_config,
            "Total des dépenses éligibles": montant_col_config,
            "Montant UE": st.column_config.ProgressColumn(
                format="%,d €",
                min_value=0,
                max_value=int(cofinancement_outliers_table["Montant UE"].max()) if len(cofinancement_outliers_table) else 1,
            ),
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
        incoherentes_table = incoherentes[
            ["Intitulé du projet", "Nom du bénéficiaire", "Fonds", "Total des dépenses éligibles", "Montant UE", "Taux de cofinancement"]
        ].head(50)
        st.dataframe(
            style_categorical_columns(incoherentes_table, {"Fonds": FONDS_COLORS}),
            hide_index=True,
            use_container_width=True,
            column_config={
                **text_widths("Intitulé du projet", "Nom du bénéficiaire"),
                "Total des dépenses éligibles": montant_col_config,
                "Montant UE": st.column_config.ProgressColumn(
                    format="%,d €", min_value=0, max_value=int(incoherentes_table["Montant UE"].max())
                ),
                "Taux de cofinancement": taux_col_config,
            },
        )
