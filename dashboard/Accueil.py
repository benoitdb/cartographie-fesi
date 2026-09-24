import pandas as pd
import plotly.express as px
import streamlit as st

from utils.analyses_controle import (
    render_cofinancement_atypique,
    render_coherence_montants,
    render_concentration_beneficiaires,
    render_dispersion,
    render_introduction_distribution,
    render_montants_atypiques,
    render_regroupements,
    render_taux_cofinancement,
    stats_col_config,
    taux_col_config,
)
from utils.carte_nationale import DROM_COM, render_carte_nationale
from utils.cofinancement import bucket_categorie, plafond_categorie
from utils.data_loader import (
    load_beneficiaires_fuzzy,
    load_data,
    load_dotations_os,
    load_geojson,
    load_interreg,
    load_programme_totals,
    load_region_metadata,
    load_transferts_solidarite,
)
from utils.filters import FONDS_OPTIONS, compute_by_region, render_fonds_filter, summarize_ops
from utils.millesime import render_millesime
from utils.pilotage import RESERVE_METHODO, build_ranking_programme_vs_engage, render_kpi_pilotage
from utils.plot_style import (
    style_hover,
)
from utils.stats import (
    build_boxplot,
    build_cofinancement_categorie_chart,
    build_cumulative_curve,
    build_fonds_barchart,
    build_portfolio_scatter,
    compute_stats_table,
    detect_beneficiaires_multi_region,
    synthese_depassements_par_region,
)
from utils.table_style import text_widths
from utils.themes import FONDS_COLORS, OBJECTIF_STRATEGIQUE_COLORS
from utils.treemap import build_hierarchy_treemap

FONDS, LEVEL1, LEVEL2 = "Fonds", "Objectif stratégique", "Objectif spécifique (Code et libellé)"

st.set_page_config(page_title="Cartographie FESI", layout="wide")

data = load_data()
geojson = load_geojson()

selected_fonds = render_fonds_filter()
render_millesime(data.get("metadata"))
filtre_actif = set(selected_fonds) != set(FONDS_OPTIONS)

st.title("Cartographie des projets FESI - Vue Nationale")

# Régions présentes dans le GeoJSON (métropole uniquement pour cette étape)
regions_metro = {f["properties"]["nom"] for f in geojson["features"]}

if filtre_actif:
    ops_selected = data["operations"][data["operations"]["Fonds"].isin(selected_fonds)]
    by_region = compute_by_region(ops_selected)
    national_summary = summarize_ops(ops_selected[ops_selected["is_national"]])
    interregional_summary = summarize_ops(ops_selected[ops_selected["is_interregional"]])
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

render_carte_nationale(by_region, geojson, color_range)

df_national_ops = data["operations"][data["operations"]["Fonds"].isin(selected_fonds)].copy()
df_national_ops[LEVEL1] = df_national_ops[LEVEL1].fillna("Non spécifié")
df_national_ops[LEVEL2] = df_national_ops[LEVEL2].fillna("Non spécifié")

mono_region = df_national_ops["regions_modernes"].apply(lambda r: isinstance(r, list) and len(r) == 1)
df_mono_region = df_national_ops[
    mono_region & ~df_national_ops["is_interregional"] & ~df_national_ops["is_national"]
].copy()
df_mono_region["Région"] = df_mono_region["regions_modernes"].apply(lambda r: r[0])

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
        st.plotly_chart(fig_fonds, width='stretch')
    with progress_col:
        st.plotly_chart(fig_cumulative, width='stretch')

    # Fonds, objectifs stratégiques et spécifiques
    st.subheader("Fonds, objectifs stratégiques et spécifiques")

    fig_hierarchy = build_hierarchy_treemap(df_national_ops, [FONDS, LEVEL1, LEVEL2])

    st.plotly_chart(fig_hierarchy, width='stretch')

    st.markdown("**Structure du portefeuille par région**")
    st.caption(
        "Nombre de projets (x) vs montant UE moyen (y), taille de bulle = montant UE total : distingue "
        "les régions portées par peu de gros projets de celles portées par de nombreux petits projets."
    )
    st.plotly_chart(build_portfolio_scatter(df_mono_region, "Région"), width='stretch')

    # Volet national
    st.subheader("Volet national")

    all_ops = data["operations"]
    national_ops = all_ops[all_ops["is_national"] & all_ops["Fonds"].isin(selected_fonds)]

    if national_ops.empty:
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
        width='stretch',
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
            width='stretch',
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
        all_ops_hab = data["operations"]
        mono_region = all_ops_hab["regions_modernes"].apply(lambda r: isinstance(r, list) and len(r) == 1)
        df_ops_par_habitant = all_ops_hab[
            all_ops_hab["Fonds"].isin(selected_fonds)
            & mono_region
            & ~all_ops_hab["is_interregional"]
            & ~all_ops_hab["is_national"]
        ].copy()
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

        st.plotly_chart(fig_par_habitant, width='stretch')
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

        st.plotly_chart(fig_consommation, width='stretch')

    st.caption(
        "Fonction comptable (certification) : depuis 2021-2027, cette fonction est intégrée à "
        "l'Autorité de gestion (règlement (UE) 2021/1060, art. 76) — il n'y a plus d'autorité de "
        "certification distincte comme sur 2014-2020, donc pas d'espace séparé pour elle ici."
    )

with tab_audit:
    render_introduction_distribution(df_national_ops, "à l'échelle nationale", "_national")

    render_taux_cofinancement(
        df_national_ops,
        "Le taux de cofinancement est plafonné réglementairement selon le fonds et la catégorie de région : "
        "le graphe ci-dessous compare le financement UE de chaque catégorie à son plafond. Un taux atypique "
        "peut signaler une opération à vérifier.",
    )

    st.markdown("**Financement UE vs plafond réglementaire, par catégorie de région**")
    st.caption(
        "Chaque catégorie de région (politique de cohésion 2021-2027) a un taux de cofinancement UE "
        "maximal réglementaire : 50% en région plus développée, 60% en transition, 85% en région moins "
        "développée ou ultrapériphérique (RUP, art. 349 TFUE) — règlement (UE) 2021/1060, art. 112. Le "
        "repère losange marque ce plafond ; plus la barre \"Financé par l'UE\" s'en rapproche, plus la "
        "catégorie consomme sa marge de cofinancement maximale autorisée."
    )
    region_metadata_categorie = load_region_metadata()
    df_categorie_source = df_mono_region.copy()
    df_categorie_source["Catégorie"] = df_categorie_source["Région"].map(
        lambda r: bucket_categorie(
            region_metadata_categorie.get(r, {}).get("categorie_ue"), region_metadata_categorie.get(r, {}).get("ultraperipherique", False)
        )
    )
    df_categorie_source["_plafond"] = df_categorie_source["Région"].map(
        lambda r: plafond_categorie(
            region_metadata_categorie.get(r, {}).get("categorie_ue"), region_metadata_categorie.get(r, {}).get("ultraperipherique", False)
        )
    )
    df_categorie = (
        df_categorie_source.dropna(subset=["_plafond"])
        .groupby("Catégorie")
        .agg(montant_ue=("Montant UE", "sum"), total_depenses=("Total des dépenses éligibles", "sum"), plafond=("_plafond", "first"))
        .reset_index()
    )
    if len(df_categorie):
        st.plotly_chart(build_cofinancement_categorie_chart(df_categorie), width='stretch')
    else:
        st.caption("Aucune catégorie de région identifiable sur le périmètre actuel.")

    # Synthèse et non liste d'opérations (#163) : ~14% des opérations mono-région dépassent le
    # plafond de leur région, une liste tronquée à 50 lignes n'en montrerait qu'une fraction
    # choisie par le tri. Le détail reste dans la Vue Régionale, qui compte avec la même fonction.
    st.markdown("**Dépassements du plafond de cofinancement, par région**")
    plafonds_region = df_categorie_source.groupby("Région")["_plafond"].first().to_dict()
    synthese_depassements = synthese_depassements_par_region(df_mono_region, plafonds_region)
    nb_hors_region = len(df_national_ops) - len(df_mono_region)
    if len(synthese_depassements):
        total_depassements = int(synthese_depassements["Dépassements"].sum())
        total_operations = int(synthese_depassements["Opérations"].sum())
        nb_depassements, nb_operations, nb_hors = (
            f"{n:,}".replace(",", " ") for n in (total_depassements, total_operations, nb_hors_region)
        )
        st.caption(
            f"{nb_depassements} opération(s) sur {nb_operations} ({total_depassements / total_operations:.0%}) "
            "ont un taux de cofinancement UE supérieur au plafond de leur région. Le plafond est fixé par axe "
            "prioritaire, pas par opération : un dépassement est un écart à expliquer, pas un constat. Pour une "
            "région mixte (ex. Auvergne-Rhône-Alpes), le plafond affiché est la moyenne pondérée de ses catégories, "
            "ce qui peut signaler des opérations régulières de la partie la mieux dotée. Le détail des opérations "
            "figure dans la Vue Régionale, onglet « Analyses & contrôle ». "
            f"{nb_hors} opération(s) interrégionale(s) ou du volet national sont hors décompte, faute "
            "de catégorie de région unique."
        )
        st.dataframe(
            synthese_depassements,
            hide_index=True,
            width='stretch',
            column_config={
                **text_widths("Région"),
                "Plafond": taux_col_config(),
                "Part": st.column_config.NumberColumn(
                    "Part des opérations", format="percent", help="Dépassements / opérations mono-région de la région"
                ),
                "Excédent UE": st.column_config.NumberColumn(
                    format="%,d €",
                    help="Montant UE au-delà de ce que le plafond autorise (Montant UE − plafond × dépenses éligibles), "
                    "sommé sur les opérations en dépassement",
                ),
            },
        )
    else:
        st.caption("Aucune région à plafond connu sur le périmètre actuel.")

    render_cofinancement_atypique(df_national_ops, colonnes_sup=("Région de l'opération",))

    echelle_box = render_dispersion(df_national_ops, "_national")

    st.markdown("**Médiane, écart-type et concentration par région**")
    stats_region = compute_stats_table(df_mono_region, "Région").rename(
        columns={"mediane": "Médiane", "ecart_type": "Écart-type", "count": "Nb projets"}
    )
    st.dataframe(
        stats_region, hide_index=True, width='stretch', column_config={**stats_col_config(), **text_widths("Région")}
    )

    st.plotly_chart(
        build_boxplot(df_mono_region, "Région", log_y=echelle_box == "Logarithmique"), width='stretch'
    )

    render_montants_atypiques(df_national_ops, colonnes_sup=("Région de l'opération",))
    render_concentration_beneficiaires(df_national_ops, "", "top_beneficiaires_national")
    render_regroupements(df_national_ops)

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
            width='stretch',
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

    render_coherence_montants(df_national_ops)
