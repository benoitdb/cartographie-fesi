"""Espace dédié à la programmation 2014-2020 (issue #83).

**Un écran, un sélecteur de périmètre** — ensemble national, volet national, ou
une région — plutôt qu'un jeu de pages miroir de celles de 2021-2027, et plutôt
qu'un sélecteur de période sur les pages existantes. Trois raisons :

- il n'y a pas de comparaison inter-périodes à outiller : les logiques de
  programmation ont changé, et le covid (REACT-EU) a déformé la fin de période
  au point de rendre un rapprochement terme à terme peu instructif ;
- Vue Régionale, Volet National et Comparateur reposent en grande partie sur les
  objectifs stratégiques et les enveloppes de l'Accord de partenariat 2021-2027,
  dont aucun n'a d'équivalent disponible ici (#79, #82) : y brancher la période
  les viderait de l'essentiel ;
- une seule entrée dans la barre latérale, et un seul périmètre à l'écran à la
  fois : ni surcharge d'affichage, ni risque de confondre les deux périodes.

Le principe posé par #83 tient toujours : **ce qui n'a pas d'équivalent ne
s'affiche pas vide, il disparaît**. Les capacités absentes sont déclarées dans
`utils/periodes.py` et récapitulées en bas de page, pour que l'absence se lise
comme un choix documenté et non comme un oubli.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.cofinancement import (
    filtrer_fonds_plafonnes,
    libelle_categorie_2014_2020,
    plafond_intervalle_2014_2020,
)
from utils.data_loader import (
    load_categories_ue_2014_2020,
    load_data_2014_2020,
    load_data_2014_2020_bretagne,
    load_data_2014_2020_normandie,
    load_data_2014_2020_nouvelle_aquitaine,
    load_data_2014_2020_pon_fse,
    load_dromcom_codes_postaux,
    load_dromcom_geojson,
    load_geojson,
    load_programme_detail_2014_2020,
    load_programme_totals_2014_2020,
    load_region_metadata,
)
from utils.departments import (
    DEPT_TO_REGION,
    assign_departments_df,
    build_department_choropleth,
    build_dromcom_outline,
    build_dromcom_projects_map,
    department_coverage_summary,
)
from utils.dromcom_localisation import build_bubbles_localisation
from utils.filters import compute_by_region, render_fonds_filter, summarize_ops
from utils.millesime import render_millesime
from utils.periodes import (
    AVERTISSEMENT_PERIMETRE,
    MENTION_BRETAGNE_FSE_GRANULARITE,
    MENTION_DEPASSEMENT_2014_2020,
    MENTION_FONDS_HORS_RAPPROCHEMENT,
    MENTION_MONTANTS_PROGRAMMES,
    MENTION_PILOTAGE_MASQUE,
    MENTION_PLAFOND_PAR_AXE,
    MENTION_PLAFONDS_PERIODE,
    MENTION_PON_FSE_NATIONAL,
    MENTION_PON_FSE_REGIONAL,
    MENTION_PROVENANCE_ENVELOPPES,
    MENTION_REACT_EU_FONDU,
    MENTION_REACT_EU_TAUX_REFERENCE,
    MENTION_REGION_MIXTE,
    MENTION_SOURCE_REGIONALE,
    PERIODE_2014_2020,
    REGIONS_PON_FSE_2014_2020,
    SOURCE_BRETAGNE_2014_2020,
    SOURCE_NORMANDIE_2014_2020,
    SOURCE_NOUVELLE_AQUITAINE_2014_2020,
    SOURCE_PON_FSE_2014_2020,
    absences_expliquees,
    appliquer_libelles_programmes,
    capacites,
    capacites_source,
    fusionner_enveloppes_sans_libelle,
    libelle_montant,
    normaliser_operations,
    pilotage_disponible,
)
from utils.pilotage import (
    build_ranking_programme_vs_engage,
    build_trajectoire,
    render_kpi_pilotage,
)
from utils.plot_style import (
    MAP_CONFIG,
    build_standalone_colorbar,
    disable_map_interaction,
    style_hover,
    style_map_background,
)
from utils.stats import (
    build_boxplot,
    build_cumulative_curve,
    build_fonds_barchart,
    build_histogram,
    build_lorenz_beneficiaires,
    build_pareto_beneficiaires,
    compute_cofinancement_table,
    compute_stats_table,
    detect_cofinancement_superieur_plafond,
    detect_incoherent_cofinancement,
    detect_outliers,
    render_top_beneficiaires_drilldown,
)
from utils.table_style import text_widths
from utils.themes import FONDS_COLORS, style_categorical_columns

FONDS = "Fonds"
MONTANT = "Montant UE"
BENEFICIAIRE = "Nom du bénéficiaire"

ENSEMBLE_NATIONAL = "Ensemble national"
VOLET_NATIONAL = "Volet national"

DROM_COM = ["Guadeloupe", "Martinique", "Guyane", "La Réunion", "Mayotte", "Saint-Martin"]

st.set_page_config(page_title="Cartographie FESI — 2014-2020", layout="wide")

data = load_data_2014_2020()
capa = capacites(PERIODE_2014_2020)
libelle_montant_ue = libelle_montant(PERIODE_2014_2020)

# Fichiers hors-Synergie lus directement par cette page pour leur périmètre (issue #95) :
# Normandie n'apparaît même pas dans `aggregates.by_region` de Synergie, Nouvelle-Aquitaine
# n'y figure qu'à la marge (25 opérations), et Bretagne (3 opérations) en est sortie à son
# tour depuis l'export officiel data.bretagne.bzh. Seul le PON FSE reste hors passe : ses
# opérations couvrent sept programmes distincts à ventiler, pas un seul périmètre régional
# (#95, point 3). None si le fichier est absent (gitignoré, non régénérable sans le XLSX
# source) : la page se rabat alors sur le sous-comptage Synergie plutôt que de planter.
SOURCE_HORS_SYNERGIE = {
    "Normandie": SOURCE_NORMANDIE_2014_2020,
    "Nouvelle-Aquitaine": SOURCE_NOUVELLE_AQUITAINE_2014_2020,
    "Bretagne": SOURCE_BRETAGNE_2014_2020,
}
data_hors_synergie = {
    "Normandie": load_data_2014_2020_normandie(),
    "Nouvelle-Aquitaine": load_data_2014_2020_nouvelle_aquitaine(),
    "Bretagne": load_data_2014_2020_bretagne(),
}

# PON FSE (issue #95, point 3) : contrairement aux trois fichiers ci-dessus, ne se
# substitue à aucun périmètre — il en **fusionne** deux catégories dedans, filtré par
# programme (REGIONS_PON_FSE_2014_2020) : les cinq PO FSE État des DROM rejoignent leur
# région, PON FSE et PO IEJ national rejoignent le Volet national. None si le fichier est
# absent (gitignoré), comme les trois autres.
data_pon_fse = load_data_2014_2020_pon_fse()

# Fonds et régions viennent des agrégats de la période : six fonds ici (FEDER,
# FSE, IEJ, FEAD, FEDER REACT-EU, FEDER-FSE) contre trois en 2021-2027, et des
# listes en dur les figeraient à ceux de l'autre période. Régions : union avec les
# périmètres hors-Synergie disponibles, pour que Normandie apparaisse enfin dans le
# sélecteur (absente de Synergie) sans dépendre du fichier XLSX pour l'ajouter.
fonds_periode = sorted(data["aggregates"]["by_fonds"])
regions_periode = sorted(
    set(data["aggregates"]["by_region"]) | {region for region, d in data_hors_synergie.items() if d is not None}
)

with st.sidebar:
    st.header("Périmètre")
    # Une clé propre à cette page : l'état des widgets est partagé entre pages
    # d'une même session, et les fonds proposés ici n'existent pas en 2021-2027.
    perimetre = st.selectbox(
        "Afficher",
        [ENSEMBLE_NATIONAL, VOLET_NATIONAL, *regions_periode],
        key="perimetre_2014_2020",
    )
selected_fonds = render_fonds_filter(options=fonds_periode, key="filtre_fonds_2014_2020")

data_regionale = data_hors_synergie.get(perimetre)
lit_source_regionale = data_regionale is not None
source_regionale = SOURCE_HORS_SYNERGIE.get(perimetre) if lit_source_regionale else None
capacite_source = capacites_source(source_regionale or PERIODE_2014_2020)

# Millésime de la source réellement affichée, pas systématiquement celui de Synergie
# (issue #95, point 1 de #95) : les trois fichiers ont chacun le leur.
render_millesime((data_regionale if lit_source_regionale else data).get("metadata"))
filtre_actif = set(selected_fonds) != set(fonds_periode)

operations = normaliser_operations(data["operations"], PERIODE_2014_2020)
ops_fonds = [op for op in operations if op.get(FONDS) in selected_fonds]

ops_fonds_regionaux = []
ops_fond_vide_normandie = []
if lit_source_regionale:
    operations_regionales = normaliser_operations(data_regionale["operations"], source_regionale)
    if perimetre == "Nouvelle-Aquitaine":
        # Ce fichier ne nomme ses programmes que par code CCI (issue #95, étape 1) : traduit
        # après le renommage des colonnes (`normaliser_operations` reste une fonction pure de
        # renommage), sur la clé canonique "Libellé Programme" qui porte alors encore le code.
        libelles_programmes = load_programme_detail_2014_2020()["libelles_programmes"]
        operations_regionales = appliquer_libelles_programmes(operations_regionales, libelles_programmes)
    if perimetre == "Normandie":
        # ~26 dossiers hors répertoire (2021-2023, probable reste à payer post-clôture —
        # voir data-pipeline/sources.py) sans `Fond` renseigné : le filtre Fonds les écarte
        # silencieusement quel que soit le fonds sélectionné, faute d'y figurer.
        ops_fond_vide_normandie = [op for op in operations_regionales if not op.get(FONDS)]
    ops_fonds_regionaux = [op for op in operations_regionales if op.get(FONDS) in selected_fonds]

ops_pon_fse_fonds = []
if data_pon_fse is not None:
    operations_pon_fse = normaliser_operations(data_pon_fse["operations"], SOURCE_PON_FSE_2014_2020)
    ops_pon_fse_fonds = [op for op in operations_pon_fse if op.get(FONDS) in selected_fonds]

# Ce périmètre reçoit-il des opérations PON FSE, et lesquelles — calculé avant le grand
# if/elif ci-dessous pour être fusionné dans chaque branche concernée (Volet national, ou
# une des cinq régions DROM) sans dupliquer la logique de routage.
if perimetre == VOLET_NATIONAL:
    ops_pon_fse_perimetre = [
        op for op in ops_pon_fse_fonds if REGIONS_PON_FSE_2014_2020.get(op.get("Libellé Programme")) is None
    ]
else:
    ops_pon_fse_perimetre = [
        op for op in ops_pon_fse_fonds if REGIONS_PON_FSE_2014_2020.get(op.get("Libellé Programme")) == perimetre
    ]

# Catégorie de cohésion de la période, et le plafond de cofinancement qui en découle.
# `.get` sur le périmètre : « Ensemble national » et « Volet national » ne sont pas des
# régions, donc pas de catégorie et pas de plafond — c'est le comportement voulu, un
# plafond n'existe qu'à la maille où une catégorie existe.
categorie_periode = load_categories_ue_2014_2020().get(perimetre)
plafond_periode = plafond_intervalle_2014_2020(categorie_periode) if capa["plafonds_cofinancement"] else None

st.title(f"FESI 2014-2020 — {perimetre}")
st.caption(MENTION_MONTANTS_PROGRAMMES)
if lit_source_regionale:
    st.info(MENTION_SOURCE_REGIONALE)
elif perimetre == VOLET_NATIONAL and ops_pon_fse_perimetre:
    st.info(MENTION_PON_FSE_NATIONAL)
elif ops_pon_fse_perimetre:
    st.info(MENTION_PON_FSE_REGIONAL)
elif not capa["perimetre_complet"]:
    st.warning(AVERTISSEMENT_PERIMETRE)

if perimetre == ENSEMBLE_NATIONAL:
    ops_perimetre = ops_fonds
elif perimetre == VOLET_NATIONAL:
    ops_perimetre = [op for op in ops_fonds if op.get("is_national")] + ops_pon_fse_perimetre
elif lit_source_regionale:
    # Le fichier régional ne couvre que ce périmètre par construction (issue #68) : pas
    # besoin du filtre regions_modernes/is_interregional/is_national de la branche Synergie
    # ci-dessous, il ne changerait rien ici. Ces trois régions n'ont pas de PO FSE État
    # dans le fichier PON FSE (ops_pon_fse_perimetre est vide) : rien à y fusionner.
    ops_perimetre = ops_fonds_regionaux
else:
    # Même découpage que la Vue Régionale 2021-2027 : les opérations
    # interrégionales et nationales sont exclues du total d'une région, sinon
    # elles seraient comptées dans plusieurs totaux censés s'additionner.
    # `ops_pon_fse_perimetre` n'ajoute quelque chose que pour les cinq DROM dont le PO FSE
    # État est routé ici (issue #95, point 3) : vide pour toute autre région.
    ops_perimetre = [
        op
        for op in ops_fonds
        if op.get("regions_modernes") == [perimetre]
        and not op.get("is_interregional")
        and not op.get("is_national")
    ] + ops_pon_fse_perimetre

if not ops_perimetre:
    st.info("Aucune opération sur ce périmètre avec les fonds sélectionnés.")
    st.stop()

df_ops = pd.DataFrame(ops_perimetre)
resume = summarize_ops(ops_perimetre)

montant_col_config = st.column_config.NumberColumn(format="%,d €")
taux_col_config = st.column_config.NumberColumn(format="percent")


def _fmt_millions(montant):
    return f"{montant / 1e6:,.1f} M€".replace(",", " ")


def _fmt_entier(valeur):
    return f"{valeur:,}".replace(",", " ")


if ops_fond_vide_normandie:
    montant_fond_vide = sum(op.get(MONTANT) or 0 for op in ops_fond_vide_normandie)
    st.caption(
        f"{_fmt_entier(len(ops_fond_vide_normandie))} opération(s) sans fonds renseigné "
        f"({_fmt_millions(montant_fond_vide)}) écartée(s) par le filtre Fonds ci-contre, quel "
        "que soit le fonds sélectionné : la colonne est vide pour ces dossiers dans le fichier "
        "source."
    )


# ---------------------------------------------------------------- Aperçu du périmètre

if perimetre == ENSEMBLE_NATIONAL:
    if filtre_actif:
        by_region = compute_by_region(ops_fonds)
        national_summary = summarize_ops([op for op in ops_fonds if op.get("is_national")])
        interregional_summary = summarize_ops([op for op in ops_fonds if op.get("is_interregional")])
    else:
        by_region = data["aggregates"]["by_region"]
        national_summary = data["aggregates"]["national"]
        interregional_summary = data["aggregates"]["interregional"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(f"{libelle_montant_ue} total", _fmt_millions(resume["montant_ue_total"]))
    col2.metric("Nombre de projets", _fmt_entier(resume["count"]))
    col3.metric("Projets en région", _fmt_entier(resume["count"] - national_summary["count"]))
    col4.metric("Volet national", _fmt_entier(national_summary["count"]))
    if interregional_summary["count"]:
        st.caption(
            f"Dont {interregional_summary['count']} opération(s) interrégionale(s) (plusieurs régions "
            "à la fois), incluses dans le total ci-dessus mais non ventilées par région ni dans le "
            "volet national. Les cinq programmes interrégionaux de la période (massifs, bassins "
            "fluviaux) tombent aujourd'hui dans le volet national faute de table massif → régions "
            "(issue #77)."
        )

    geojson = load_geojson()
    regions_metro = {f["properties"]["nom"] for f in geojson["features"]}

    # Même échelle de couleur pour la métropole et les vignettes DROM-COM : colorer
    # chaque vignette sur son seul montant ferait ressortir un petit territoire aussi
    # foncé qu'une grande région bien plus dotée.
    montants_nationaux = [v["montant_ue_total"] for region, v in by_region.items() if region in regions_metro or region in DROM_COM]
    color_range = [0, max(montants_nationaux)] if montants_nationaux else [0, 1]

    # Pas de `.lower()` sur le libellé : il commence par le sigle « UE », qu'une
    # mise en minuscules transformerait en « montant ue programmé ».
    st.subheader(f"Répartition géographique — {libelle_montant_ue}")
    st.caption(
        "Le rattachement à une région vient du **libellé du programme** et non de la colonne "
        "région, remplie à 16,4 % seulement dans cette source — les programmes d'avant la fusion "
        "des régions de 2016 sont ramenés à leur région actuelle. Les régions quasi vides le sont "
        "pour la raison indiquée plus haut : leur autorité de gestion n'était pas dans Synergie."
    )

    col_legend, col_metro, col_dromcom = st.columns([1, 4, 6])

    with col_legend:
        st.plotly_chart(
            # « Montant UE (€) » et non le libellé long de la période : la colonne de
            # légende est étroite, un titre plus long y est tronqué (« Montant UE pr »).
            build_standalone_colorbar(color_range, "Montant UE (€)", height=480),
            width='stretch',
            config={"displayModeBar": False},
        )

    with col_metro:
        st.markdown("**France métropolitaine**")
        df_carte = pd.DataFrame(
            [
                {"region": region, "montant_ue_total": v["montant_ue_total"], "count": v["count"]}
                for region, v in by_region.items()
                if region in regions_metro
            ]
        )
        fig_carte = px.choropleth(
            df_carte,
            geojson=geojson,
            locations="region",
            featureidkey="properties.nom",
            color="montant_ue_total",
            color_continuous_scale="Blues",
            range_color=color_range,
            custom_data=["count"],
            labels={"montant_ue_total": f"{libelle_montant_ue} (€)"},
        )
        fig_carte.update_traces(
            hovertemplate=f"<b>%{{location}}</b><br>{libelle_montant_ue} : %{{z:,.0f}} €<br>Nb projets : %{{customdata[0]}}<extra></extra>"
        )
        fig_carte.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
        fig_carte.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=480, coloraxis_showscale=False)
        st.plotly_chart(
            disable_map_interaction(style_map_background(style_hover(fig_carte))),
            width='stretch',
            config=MAP_CONFIG,
        )

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
                    hovertemplate=f"<b>{territoire}</b><br>{libelle_montant_ue} : %{{z:,.0f}} €<extra></extra>"
                )
                fig_dromcom.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
                fig_dromcom.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=135, coloraxis_showscale=False)
                st.plotly_chart(
                    disable_map_interaction(style_map_background(style_hover(fig_dromcom))),
                    width='stretch',
                    config=MAP_CONFIG,
                )
                if valeurs["count"]:
                    st.caption(f"{_fmt_millions(valeurs['montant_ue_total'])} · {valeurs['count']} projets")
                else:
                    st.caption("Aucun projet")

elif perimetre == VOLET_NATIONAL:
    col1, col2, col3 = st.columns(3)
    col1.metric(f"{libelle_montant_ue} total", _fmt_millions(resume["montant_ue_total"]))
    col2.metric("Nombre de projets", _fmt_entier(resume["count"]))
    col3.metric("Programmes", _fmt_entier(df_ops["Libellé Programme"].nunique()))
    st.caption(
        "Opérations rattachées à aucune région en particulier : programmes nationaux, "
        "assistance technique, et — faute de table massif → régions — les cinq programmes "
        "interrégionaux de la période (issue #77)."
    )

else:
    region_meta = load_region_metadata().get(perimetre)
    est_metropole = perimetre in DEPT_TO_REGION.values()

    col1, col2, col3 = st.columns(3)
    col1.metric(f"{libelle_montant_ue} total", _fmt_millions(resume["montant_ue_total"]))
    col2.metric("Nombre de projets", _fmt_entier(resume["count"]))
    col3.metric("Bénéficiaires", _fmt_entier(df_ops[BENEFICIAIRE].nunique()))

    apercu_col1, apercu_col2 = st.columns([1, 2])
    with apercu_col1:
        if region_meta:
            with st.container(border=True):
                st.markdown(f"**Population :** {_fmt_entier(region_meta['population'])} ({region_meta['population_year']})")
                st.markdown(f"**Superficie :** {_fmt_entier(round(region_meta['superficie_km2']))} km²")
                st.markdown(f"**Chef-lieu :** {region_meta['chef_lieu']}")
            # Catégorie **de la période**, et surtout pas `region_meta["categorie_ue"]`,
            # qui est celle de 2021-2027 : les deux découpages diffèrent, et l'un affiché
            # à la place de l'autre serait une donnée réglementaire fausse sans rien
            # casser à l'écran (issue #81).
            st.markdown(f"**Catégorie UE 2014-2020 :** {libelle_categorie_2014_2020(categorie_periode)}")
            st.caption(
                "Catégorie au sens de la politique de cohésion **2014-2020** (décision "
                "d'exécution 2014/99/UE), qui détermine le plafond de cofinancement de la "
                "période. Ce n'est pas celle de 2021-2027 : le découpage a changé, les dix "
                "régions métropolitaines « en transition » d'alors n'existent plus sous cette "
                "forme."
            )
            if categorie_periode and not categorie_periode.get("categorie_ue"):
                st.caption(MENTION_REGION_MIXTE)

    afficher_detail_dept = False
    with apercu_col2:
        if est_metropole and capacite_source["departement"]:
            # La carte et son détail (légende, tableau) ont besoin de toute la largeur de
            # la page — voir la section « Détail par département » plus bas, même principe
            # que la page 1 (`1_Vue_Régionale.py`).
            afficher_detail_dept = True
        elif est_metropole:
            # Pas de code postal ni de département dans ce fichier régional (Nouvelle-
            # Aquitaine) : aucun rattachement, même approché, n'est possible — la carte
            # disparaît plutôt que de s'afficher entièrement « inconnu » (issue #95).
            st.info(
                "**Pas de carte départementale sur ce périmètre.** Le fichier régional ne "
                "porte ni code postal ni département."
            )
        else:
            bulles, couverture = build_bubbles_localisation(ops_perimetre, perimetre, load_dromcom_codes_postaux())
            dromcom_geojson = load_dromcom_geojson()
            if len(bulles):
                st.plotly_chart(
                    build_dromcom_projects_map(perimetre, dromcom_geojson, bulles),
                    width='stretch',
                    config=MAP_CONFIG,
                )
                st.caption(
                    "Une bulle par code postal, taille proportionnelle au montant cumulé. "
                    "Origine de la localisation : "
                    + " · ".join(f"{source} : {_fmt_entier(nb)}" for source, nb in couverture.items() if nb)
                    + "."
                )
            else:
                st.plotly_chart(
                    build_dromcom_outline(perimetre, dromcom_geojson),
                    width='stretch',
                    config=MAP_CONFIG,
                )
                st.caption("Aucune opération localisable par code postal sur ce périmètre.")

    if afficher_detail_dept:
        st.subheader("Détail par département")

        df_region_dept = assign_departments_df(df_ops)
        # department_coverage_summary renvoie des **parts**, pas des effectifs. Le
        # seuil à 0,5 % évite d'afficher « inconnu : 0 % », qui occupe une place
        # pour ne rien dire.
        couverture_dept = department_coverage_summary(df_region_dept)
        depts_perimetre = {code for code, r in DEPT_TO_REGION.items() if r == perimetre}
        hors_perimetre = df_region_dept["dept"].notna() & ~df_region_dept["dept"].isin(depts_perimetre)
        part_hors_perimetre = hors_perimetre.sum() / len(df_region_dept) if len(df_region_dept) else 0
        st.caption(
            "Origine du rattachement : "
            + " · ".join(f"{source} : {part:.0%}" for source, part in couverture_dept.items() if part >= 0.005)
            + ". La colonne « Département de l'opération » est peu renseignée sur cette "
            "période : l'essentiel du rattachement est **approché** depuis le code postal du "
            "bénéficiaire, puis depuis son nom — le siège du bénéficiaire, donc, et pas "
            "nécessairement le lieu du projet. "
            + (
                f"{part_hors_perimetre:.0%} des opérations pointent vers un département situé "
                f"hors de {perimetre} (ligne « Hors périmètre » ci-dessous) — le rattachement "
                "régional reste fiable, seul le département est en cause."
                if hors_perimetre.any()
                else ""
            )
        )

        non_reparti = df_region_dept[df_region_dept["dept"].isna()]
        non_reparti_montant = non_reparti[MONTANT].sum()
        non_reparti_count = len(non_reparti)

        df_dept_connu = df_region_dept[df_region_dept["dept"].notna() & df_region_dept["dept"].isin(depts_perimetre)]
        dept_table = (
            df_dept_connu.groupby("dept")
            .agg(montant_ue_total=(MONTANT, "sum"), count=(MONTANT, "count"))
            .reset_index()
            .rename(columns={"dept": "Département", "montant_ue_total": "Montant UE total", "count": "Nb projets"})
            .sort_values("Montant UE total", ascending=False)
        )
        # Échelle calée sur les seuls départements du périmètre (avant l'ajout des lignes
        # "Non réparti"/"Hors périmètre" ci-dessous, qui ne correspondent à aucun département
        # sur la carte) — même échelle que la carte donc.
        color_range_dept = [0, dept_table["Montant UE total"].max()] if len(dept_table) else [0, 1]
        # Les deux lignes suivantes complètent le tableau à 100 % du périmètre : sans elles,
        # les opérations sans département connu ou rattachées à un département d'une autre
        # région disparaîtraient silencieusement du total affiché (issue #100).
        if non_reparti_count:
            dept_table = pd.concat(
                [
                    dept_table,
                    pd.DataFrame(
                        [{"Département": "Non réparti (région entière)", "Montant UE total": non_reparti_montant, "Nb projets": non_reparti_count}]
                    ),
                ],
                ignore_index=True,
            )
        if hors_perimetre.any():
            df_hors_perimetre = df_region_dept[hors_perimetre]
            dept_table = pd.concat(
                [
                    dept_table,
                    pd.DataFrame(
                        [
                            {
                                "Département": "Hors périmètre (autre région)",
                                "Montant UE total": df_hors_perimetre[MONTANT].sum(),
                                "Nb projets": len(df_hors_perimetre),
                            }
                        ]
                    ),
                ],
                ignore_index=True,
            )

        # Légende + carte + tableau côte à côte, comme sur la page 1 (`1_Vue_Régionale.py`) :
        # la carte désactive son colorbar intégré au profit d'une légende commune.
        col_legend_dept, col_map_dept, col_table_dept = st.columns([1, 4, 5])
        with col_legend_dept:
            st.plotly_chart(
                build_standalone_colorbar(color_range_dept, "Montant UE (€)", height=420),
                width='stretch',
                config={"displayModeBar": False},
            )
        with col_map_dept:
            st.plotly_chart(
                build_department_choropleth(df_region_dept, perimetre, show_colorbar=False),
                width='stretch',
                config=MAP_CONFIG,
            )
        with col_table_dept:
            st.dataframe(
                dept_table,
                hide_index=True,
                width='stretch',
                column_config={
                    **text_widths("Département"),
                    "Montant UE total": st.column_config.ProgressColumn(
                        format="%,d €",
                        min_value=0,
                        max_value=int(dept_table["Montant UE total"].max()) if len(dept_table) else 1,
                    ),
                },
            )

# ---------------------------------------------------------------- Analyses

# Trois onglets comme les pages 2021-2027 depuis que les dotations de la période
# sont transcrites (#93). L'onglet Pilotage existe sur tous les périmètres, mais il
# n'affiche un taux que là où l'engagé est comparable à l'enveloppe : ailleurs il
# porte l'explication à la place. C'est l'arbitrage inverse de #83 — un onglet
# absent ne s'explique pas, un onglet qui dit pourquoi il est vide, si.

# Calculé avant les onglets : la Vue d'ensemble (segment « Reste à engager », repère
# programmé de la courbe cumulée) et le Pilotage s'appuient tous les deux sur la même
# enveloppe programmée de la période.
#
# Normandie et Nouvelle-Aquitaine ne sont pilotables que si leur fichier régional a pu
# être chargé (issue #95) : sans lui, l'engagé disponible resterait celui, très partiel,
# de Synergie — `pilotage_disponible` seule ne le sait pas, elle ne connaît que la
# période, pas la disponibilité d'un fichier sur ce poste.
#
# « Ensemble national » reste masqué (aucune de ses régions hors-Synergie n'y est
# fusionnée, seul le fait pour son propre périmètre — voir ops_perimetre plus haut) ;
# « Volet national » ne l'est plus depuis que PON FSE y est fusionné (issue #95, point
# 3) : c'était la seule pièce manquante pour lui opposer un engagé complet, comme
# l'annonçait déjà MENTION_PILOTAGE_MASQUE ("la reprise de ce point... suivie en #95").
perimetre_pilotable = pilotage_disponible(
    perimetre, est_national=perimetre == ENSEMBLE_NATIONAL
) and not (perimetre in SOURCE_HORS_SYNERGIE and not lit_source_regionale)

enveloppes_perimetre = {}
fonds_fusionnes = set()
if perimetre_pilotable:
    # Les JSON d'enveloppes indexent les CCI sans région sous la clé "national", pas le
    # libellé de ce périmètre (même convention que Page 2, Volet National 2021-2027).
    cle_enveloppe = "national" if perimetre == VOLET_NATIONAL else perimetre
    enveloppes_perimetre = load_programme_totals_2014_2020().get(cle_enveloppe, {})
    # Une enveloppe dont aucun libellé de fonds ne porte d'opération ici rejoint son
    # fonds d'origine : sans ça, la métropole afficherait un FEDER REACT-EU à 0 % et
    # un FEDER gonflé de la même somme (voir la règle et ses chiffres dans periodes.py).
    enveloppes_perimetre, fonds_fusionnes = fusionner_enveloppes_sans_libelle(
        enveloppes_perimetre, set(df_ops[FONDS].unique())
    )

tab_ensemble, tab_pilotage, tab_audit = st.tabs(["Vue d'ensemble", "Pilotage", "Analyses & contrôle"])

with tab_ensemble:
    st.subheader("Répartition par fonds")
    st.caption(
        "Six fonds sur cette période, contre trois en 2021-2027 : le FSE devient FSE+, l'IEJ "
        "et le FEAD n'ont pas de successeur direct, et le FTJ n'existait pas. **FEDER REACT-EU** "
        "est l'instrument de relance post-covid, doté d'un régime de financement propre."
    )

    df_fonds = (
        df_ops.groupby(FONDS)
        .agg(montant_ue_total=(MONTANT, "sum"), count=(MONTANT, "count"))
        .reset_index()
        .rename(columns={FONDS: "fonds"})
        .sort_values("montant_ue_total")
    )

    col_barres, col_courbe = st.columns([1, 3])
    with col_barres:
        # totaux_programme=None (fonds sans enveloppe fiable, ou pilotage masqué sur ce
        # périmètre — #95) : pas de segment « reste à engager » ni de repère programmé,
        # même repli que `build_fonds_barchart` sans donnée. Depuis #93, l'enveloppe existe
        # dès que `perimetre_pilotable`, calculée une fois pour la Vue d'ensemble et le
        # Pilotage juste avant les onglets.
        fig_fonds = build_fonds_barchart(
            df_fonds, FONDS_COLORS, totaux_programme=enveloppes_perimetre if perimetre_pilotable else None
        )
        fig_fonds.update_layout(height=400)
        st.plotly_chart(fig_fonds, width='stretch')
    with col_courbe:
        mode_courbe = st.radio("Courbe cumulée", ["Montant", "%"], horizontal=True, key="mode_courbe_2014_2020")
        mode_courbe_val = "pourcentage" if mode_courbe == "%" else "montant"
        st.plotly_chart(
            build_cumulative_curve(
                df_ops,
                color_map=FONDS_COLORS,
                totaux_ref=enveloppes_perimetre if perimetre_pilotable else None,
                mode=mode_courbe_val,
            ),
            width='stretch',
        )
        st.caption(
            "Montant UE programmé cumulé dans le temps, d'après la date de début de "
            "l'opération. Les programmations s'étalent jusqu'en 2023 : conventionnements "
            "tardifs et mobilisation de REACT-EU en fin de période. **La période d'une "
            "opération se lit à son fonds et à son programme, jamais à sa date.** En mode "
            "%, seuls les fonds avec une enveloppe programmée connue sont affichés."
        )

    if perimetre == ENSEMBLE_NATIONAL:
        st.subheader("Classement des régions")
        df_regions = (
            pd.DataFrame(
                [
                    {"Région": region, libelle_montant_ue: v["montant_ue_total"], "Nb projets": v["count"]}
                    for region, v in by_region.items()
                ]
            )
            .sort_values(libelle_montant_ue, ascending=False)
            .reset_index(drop=True)
        )
        st.dataframe(
            df_regions,
            width='stretch',
            hide_index=True,
            column_config={
                libelle_montant_ue: st.column_config.ProgressColumn(
                    format="%,d €",
                    min_value=0,
                    max_value=int(df_regions[libelle_montant_ue].max()) if len(df_regions) else 1,
                )
            },
        )
        st.caption(
            "À lire avec l'avertissement de périmètre en haut de page : les régions dont "
            "l'autorité de gestion n'était pas dans Synergie sont sous-comptées ici."
        )

    st.subheader("Programmes")
    df_programmes = (
        df_ops.groupby("Libellé Programme")
        .agg(**{libelle_montant_ue: (MONTANT, "sum"), "Nb projets": (MONTANT, "count")})
        .reset_index()
        .sort_values(libelle_montant_ue, ascending=False)
    )
    st.dataframe(
        df_programmes,
        width='stretch',
        hide_index=True,
        column_config={
            **text_widths("Libellé Programme"),
            libelle_montant_ue: st.column_config.ProgressColumn(
                format="%,d €",
                min_value=0,
                max_value=int(df_programmes[libelle_montant_ue].max()) if len(df_programmes) else 1,
            ),
        },
    )
    st.caption(
        "Le programme est ce qui rattache une opération à sa région sur cette période, et ce "
        "qui la situe dans une programmation — pas sa date."
    )

with tab_pilotage:
    st.subheader("Pilotage : programmé vs engagé")

    # perimetre_pilotable calculé une fois, juste avant les onglets (voir le commentaire
    # à cet endroit pour le détail des cas masqués — #95).
    if not perimetre_pilotable:
        st.info(MENTION_PILOTAGE_MASQUE)
    else:
        # enveloppes_perimetre, cle_enveloppe et fonds_fusionnes sont calculés une fois,
        # juste avant les onglets (partagés avec la Vue d'ensemble).
        #
        # Fonds rapprochables = ceux qui ont une enveloppe **et** sont sélectionnés.
        # Le FEAD et le FEDER-FSE n'en ont pas (voir MENTION_FONDS_HORS_RAPPROCHEMENT) :
        # ils sortent du rapprochement des deux côtés à la fois, numérateur compris —
        # les laisser dans l'engagé gonflerait le taux d'un montant sans dénominateur,
        # exactement le piège que l'issue #93 devait éviter pour REACT-EU.
        fonds_rapprochables = [f for f in sorted(enveloppes_perimetre) if f in selected_fonds]
        engage_par_fonds = df_ops.groupby(FONDS)[MONTANT].sum().to_dict()

        df_fonds_pilotage = pd.DataFrame(
            [
                {"fonds": f, "engage": engage_par_fonds.get(f, 0), "programme": enveloppes_perimetre[f]}
                for f in fonds_rapprochables
            ]
        )

        if df_fonds_pilotage.empty:
            st.info(
                "Aucun des fonds sélectionnés n'a d'enveloppe programmée sur ce périmètre. "
                "Sélectionnez le FEDER, le FSE, l'IEJ ou le FEDER REACT-EU pour afficher un "
                "taux de consommation."
            )
        else:
            montant_programme = int(df_fonds_pilotage["programme"].sum())
            montant_engage = int(df_fonds_pilotage["engage"].sum())
            render_kpi_pilotage(
                df_fonds_pilotage,
                montant_programme,
                montant_engage,
                color_map=FONDS_COLORS,
                libelle_programme="Programmé 2014-2020",
                reserve_methodo=MENTION_PROVENANCE_ENVELOPPES,
                mention_depassement=MENTION_DEPASSEMENT_2014_2020,
            )
            st.caption(MENTION_FONDS_HORS_RAPPROCHEMENT)
            if fonds_fusionnes:
                st.caption(MENTION_REACT_EU_FONDU)
            if perimetre == "Bretagne" and "FSE" in fonds_rapprochables:
                st.caption(MENTION_BRETAGNE_FSE_GRANULARITE)

            detail_react_eu = load_programme_detail_2014_2020()
            part_react_eu_brut = detail_react_eu["react_eu"].get(cle_enveloppe, {})
            part_react_eu = {f: v for f, v in part_react_eu_brut.items() if f in fonds_rapprochables}
            if part_react_eu:
                detail = ", ".join(f"{f} {v / 1e6:,.1f} M€".replace(",", " ") for f, v in sorted(part_react_eu.items()))
                st.caption(
                    f"Dont maquettes REACT-EU incluses dans les enveloppes ci-dessus : {detail}. "
                    "Leur provenance (évaluation ANCT, 2024) diffère de celle du reste "
                    "(Accord de partenariat, 2019)."
                )

            # Taux indépendant des opérations Synergie (issue #96), gardé sur le choix
            # explicite de fonds (`selected_fonds`) et non sur `fonds_rapprochables` : c'est
            # justement pour le FEDER REACT-EU fondu en métropole (MENTION_REACT_EU_FONDU,
            # absent de `part_react_eu` ci-dessus) que cette référence a le plus de valeur.
            part_react_eu_justifie = detail_react_eu["react_eu_justifie"].get(cle_enveloppe, {})
            taux_reference = {
                f: part_react_eu_justifie[f] / part_react_eu_brut[f]
                for f in part_react_eu_brut
                if f in part_react_eu_justifie and f in selected_fonds
            }
            if taux_reference:
                detail_taux = ", ".join(f"{f} {t:.0%}" for f, t in sorted(taux_reference.items()))
                st.caption(MENTION_REACT_EU_TAUX_REFERENCE.format(detail=detail_taux))

            if capacite_source["trajectoire"]:
                traj_col, bullet_col = st.columns(2)
                with traj_col:
                    # `Date de programmation` et non la date de début : sur cette période c'est
                    # elle qui date l'engagement, la date de référence n'étant pas la même qu'en
                    # 2021-2027 (première convention) — cf. profil de source, issue #69.
                    st.plotly_chart(
                        build_trajectoire(
                            df_ops[df_ops[FONDS].isin(fonds_rapprochables)],
                            montant_programme,
                            date_col="Date de programmation",
                        ),
                        width='stretch',
                    )
                with bullet_col:
                    st.plotly_chart(
                        build_ranking_programme_vs_engage(df_fonds_pilotage, "fonds", "engage", "programme", height=400),
                        width='stretch',
                    )
                if ops_pon_fse_perimetre:
                    # Voir MENTION_PON_FSE_REGIONAL/NATIONAL en haut de page : ce fichier n'a
                    # pas de date de programmation, ses opérations disparaissent silencieusement
                    # du groupby de build_trajectoire (NaT). Le rappeler ici, où le manque se
                    # voit sans que le lecteur remonte au haut de page.
                    st.caption(
                        "La courbe de trajectoire n'inclut pas les opérations du programme "
                        "opérationnel national FSE (pas de date de programmation) : elle sous-"
                        "compte l'engagé réel affiché ci-dessus."
                    )
            else:
                # Pas de `Date de programmation` dans ce fichier régional : la trajectoire
                # disparaît plutôt que d'être reconstruite depuis la date de **début**
                # d'opération, qui ne date pas la même chose (cf. la mise en garde de la
                # section "Répartition par fonds" plus haut) — un substitut daterait
                # l'engagement à un autre stade sans le dire.
                st.plotly_chart(
                    build_ranking_programme_vs_engage(df_fonds_pilotage, "fonds", "engage", "programme", height=400),
                    width='stretch',
                )
                st.caption(
                    "Pas de trajectoire dans le temps sur ce périmètre : le fichier régional "
                    "ne porte pas de date de programmation."
                )


with tab_audit:
    st.caption(
        "Dispersion des montants, concentration par bénéficiaire et cohérence des montants — "
        "des repères usuels pour l'analyse d'un portefeuille. Un écart signalé est un point à "
        "expliquer, pas une conclusion."
    )

    st.subheader("Statistiques par fonds")
    stats_fonds = compute_stats_table(df_ops, FONDS)
    st.dataframe(
        style_categorical_columns(stats_fonds, {FONDS: FONDS_COLORS}),
        width='stretch',
        hide_index=True,
        column_config={
            "Médiane": montant_col_config,
            "Écart-type": montant_col_config,
            "cv": st.column_config.NumberColumn(
                "Coeff. de variation",
                help="Écart-type / médiane — dispersion relative, comparable entre groupes de tailles différentes",
            ),
            "concentration_top10": st.column_config.NumberColumn(
                "Concentration (top 10%)",
                format="percent",
                help="Part du montant total portée par les 10% de projets les plus importants du groupe",
            ),
        },
    )

    col_hist, col_box = st.columns(2)
    with col_hist:
        st.markdown("**Distribution des montants**")
        st.plotly_chart(
            build_histogram(df_ops, log_x=True, color_col=FONDS, color_map=FONDS_COLORS),
            width='stretch',
        )
        st.caption("Échelle logarithmique : les montants s'étalent sur plusieurs ordres de grandeur.")
    with col_box:
        st.markdown("**Dispersion par fonds**")
        st.plotly_chart(build_boxplot(df_ops, FONDS, log_y=True, color_map=FONDS_COLORS), width='stretch')

    st.subheader("Valeurs atypiques")
    # group_col=FONDS : des bornes IQR communes à six fonds d'ordres de grandeur très
    # différents signaleraient des opérations parfaitement ordinaires (constaté en
    # 2021-2027, où 502 opérations FEDER l'étaient à tort).
    atypiques = detect_outliers(df_ops, group_col=FONDS)
    st.caption(
        f"{len(atypiques)} opération(s) au montant atypique par rapport aux autres opérations "
        "**du même fonds** (méthode IQR)."
    )
    table_atypiques = atypiques[["Intitulé du projet", BENEFICIAIRE, FONDS, MONTANT]].rename(
        columns={MONTANT: libelle_montant_ue}
    )
    st.dataframe(
        style_categorical_columns(table_atypiques, {FONDS: FONDS_COLORS}),
        width='stretch',
        hide_index=True,
        column_config={
            **text_widths("Intitulé du projet", BENEFICIAIRE),
            libelle_montant_ue: st.column_config.ProgressColumn(
                format="%,d €",
                min_value=0,
                max_value=int(table_atypiques[libelle_montant_ue].max()) if len(table_atypiques) else 1,
            ),
        },
    )

    st.subheader("Concentration par bénéficiaire")
    render_top_beneficiaires_drilldown(df_ops, montant_col_config, key="top_benef_2014_2020")

    col_pareto, col_lorenz = st.columns(2)
    with col_pareto:
        st.plotly_chart(build_pareto_beneficiaires(df_ops), width='stretch')
    with col_lorenz:
        st.plotly_chart(build_lorenz_beneficiaires(df_ops), width='stretch')

    st.subheader("Taux de cofinancement UE")
    # Le fichier 2014-2020 ne porte pas de colonne de taux : il est dérivé du montant UE
    # et des dépenses éligibles (utils/periodes.normaliser_operations), un simple quotient
    # de deux colonnes présentes.
    st.caption(MENTION_PLAFONDS_PERIODE)
    cofi_fonds = compute_cofinancement_table(df_ops, FONDS).rename(
        columns={"taux_moyen": "Taux moyen", "taux_median": "Taux médian", "count": "Nb projets"}
    )
    st.dataframe(
        style_categorical_columns(cofi_fonds, {FONDS: FONDS_COLORS}),
        width='stretch',
        hide_index=True,
        column_config={
            "Taux moyen": st.column_config.ProgressColumn(
                format="percent", min_value=0, max_value=max(1.0, cofi_fonds["Taux moyen"].max())
            ),
            "Taux médian": taux_col_config,
        },
    )

    # Le plafond n'existe qu'à la maille d'une région : les périmètres agrégés réunissent
    # des catégories différentes, et il n'y a pas de plafond « moyen » à opposer à une
    # opération. Plutôt qu'un tableau sans borne et sans explication, on dit à quelle
    # maille l'information existe.
    if plafond_periode is None:
        st.info(
            "**Pas de plafond opposable sur ce périmètre.** Le plafond de cofinancement "
            "2014-2020 découle de la catégorie de la région, or ce périmètre en réunit "
            "plusieurs (ensemble national) ou n'est rattaché à aucune (volet national : "
            "programmes nationaux, assistance technique, programmes interrégionaux). "
            "Sélectionner une région dans la barre latérale affiche son plafond et les "
            "opérations qui le dépassent."
        )
    else:
        plafond_min, plafond_max = plafond_periode
        df_plafonnees, nb_hors_plafond = filtrer_fonds_plafonnes(df_ops, fonds_col=FONDS)

        if plafond_min == plafond_max:
            st.markdown(f"**Plafond applicable : {plafond_min:.0%}** — {libelle_categorie_2014_2020(categorie_periode)}.")
        else:
            # Fourchette, et le dépassement est compté sur la borne **haute** : sous la
            # borne basse, une opération peut parfaitement relever de l'ancienne région
            # à plafond élevé. Compter sur la borne basse produirait des « dépassements »
            # dont on sait qu'ils sont peut-être réguliers — l'inverse de ce qu'on cherche.
            st.markdown(f"**Plafond applicable : entre {plafond_min:.0%} et {plafond_max:.0%}** selon l'ancienne région.")
            st.caption(MENTION_REGION_MIXTE)

        if nb_hors_plafond:
            st.caption(
                f"{_fmt_entier(nb_hors_plafond)} opération(s) écartée(s) du décompte ci-dessous "
                "(FEDER REACT-EU, IEJ, FEAD) : leur régime n'est pas celui de l'article 120. "
                "Elles restent comptées dans le tableau des taux par fonds ci-dessus, qui est "
                "descriptif."
            )

        depassements = detect_cofinancement_superieur_plafond(df_plafonnees, plafond_max)
        st.caption(f"{_fmt_entier(len(depassements))} opération(s) au taux supérieur à {plafond_max:.0%}.")
        if len(depassements):
            st.caption(MENTION_PLAFOND_PAR_AXE)
        if len(depassements):
            st.dataframe(
                style_categorical_columns(
                    depassements[
                        ["Intitulé du projet", BENEFICIAIRE, FONDS, "Total des dépenses éligibles", MONTANT, "Taux de cofinancement"]
                    ].head(50),
                    {FONDS: FONDS_COLORS},
                ),
                width='stretch',
                hide_index=True,
                column_config={
                    **text_widths("Intitulé du projet", BENEFICIAIRE),
                    "Total des dépenses éligibles": montant_col_config,
                    MONTANT: montant_col_config,
                    "Taux de cofinancement": taux_col_config,
                },
            )

    st.markdown("**Cohérence des montants**")
    st.caption(
        "Opérations dont le montant UE dépasse le total des dépenses éligibles, ce qui "
        "correspondrait à un taux de cofinancement supérieur à 100 % — impossible quel que "
        "soit le fonds, y compris REACT-EU dont le régime propre plafonne justement à 100 %."
    )
    incoherentes = detect_incoherent_cofinancement(df_ops)
    if len(incoherentes):
        st.dataframe(
            style_categorical_columns(
                incoherentes[
                    ["Intitulé du projet", BENEFICIAIRE, FONDS, "Total des dépenses éligibles", MONTANT, "Taux de cofinancement"]
                ],
                {FONDS: FONDS_COLORS},
            ),
            width='stretch',
            hide_index=True,
            column_config={
                **text_widths("Intitulé du projet", BENEFICIAIRE),
                "Total des dépenses éligibles": montant_col_config,
                MONTANT: montant_col_config,
                "Taux de cofinancement": taux_col_config,
            },
        )
    else:
        st.success("Aucune incohérence détectée sur le périmètre affiché.")

absences = absences_expliquees(PERIODE_2014_2020)
if absences:
    with st.expander("Ce que cet espace n'affiche pas, et pourquoi"):
        st.markdown(
            "Des blocs présents sur les pages 2021-2027 sont **absents** ici, plutôt "
            "qu'affichés vides — une dimension absente de la source ne doit pas ressembler "
            "à une dimension mesurée et nulle :\n\n"
            + "\n".join(f"- {texte}" for texte in absences)
            + "\n\nLe détail des quatre sources hors Synergie, non fusionnées à ce jeu de "
            "données, est consultable sur la page « Validation de la source » (issue #68)."
        )
