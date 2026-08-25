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
    load_dromcom_codes_postaux,
    load_dromcom_geojson,
    load_geojson,
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
    MENTION_MONTANTS_PROGRAMMES,
    MENTION_PLAFOND_PAR_AXE,
    MENTION_PLAFONDS_PERIODE,
    MENTION_REGION_MIXTE,
    PERIODE_2014_2020,
    absences_expliquees,
    capacites,
    libelle_montant,
    normaliser_operations,
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

# Fonds et régions viennent des agrégats de la période : six fonds ici (FEDER,
# FSE, IEJ, FEAD, FEDER REACT-EU, FEDER-FSE) contre trois en 2021-2027, et des
# listes en dur les figeraient à ceux de l'autre période.
fonds_periode = sorted(data["aggregates"]["by_fonds"])
regions_periode = sorted(data["aggregates"]["by_region"])

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
render_millesime(data.get("metadata"))
filtre_actif = set(selected_fonds) != set(fonds_periode)

operations = normaliser_operations(data["operations"], PERIODE_2014_2020)
ops_fonds = [op for op in operations if op.get(FONDS) in selected_fonds]

# Catégorie de cohésion de la période, et le plafond de cofinancement qui en découle.
# `.get` sur le périmètre : « Ensemble national » et « Volet national » ne sont pas des
# régions, donc pas de catégorie et pas de plafond — c'est le comportement voulu, un
# plafond n'existe qu'à la maille où une catégorie existe.
categorie_periode = load_categories_ue_2014_2020().get(perimetre)
plafond_periode = plafond_intervalle_2014_2020(categorie_periode) if capa["plafonds_cofinancement"] else None

st.title(f"FESI 2014-2020 — {perimetre}")
st.caption(MENTION_MONTANTS_PROGRAMMES)
if not capa["perimetre_complet"]:
    st.warning(AVERTISSEMENT_PERIMETRE)

if perimetre == ENSEMBLE_NATIONAL:
    ops_perimetre = ops_fonds
elif perimetre == VOLET_NATIONAL:
    ops_perimetre = [op for op in ops_fonds if op.get("is_national")]
else:
    # Même découpage que la Vue Régionale 2021-2027 : les opérations
    # interrégionales et nationales sont exclues du total d'une région, sinon
    # elles seraient comptées dans plusieurs totaux censés s'additionner.
    ops_perimetre = [
        op
        for op in ops_fonds
        if op.get("regions_modernes") == [perimetre]
        and not op.get("is_interregional")
        and not op.get("is_national")
    ]

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
            use_container_width=True,
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
            use_container_width=True,
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
                    use_container_width=True,
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

    with apercu_col2:
        if est_metropole:
            df_region_dept = assign_departments_df(df_ops)
            st.plotly_chart(
                build_department_choropleth(df_region_dept, perimetre),
                use_container_width=True,
                config=MAP_CONFIG,
            )
        else:
            df_region_dept = None
            bulles, couverture = build_bubbles_localisation(ops_perimetre, perimetre, load_dromcom_codes_postaux())
            dromcom_geojson = load_dromcom_geojson()
            if len(bulles):
                st.plotly_chart(
                    build_dromcom_projects_map(perimetre, dromcom_geojson, bulles),
                    use_container_width=True,
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
                    use_container_width=True,
                    config=MAP_CONFIG,
                )
                st.caption("Aucune opération localisable par code postal sur ce périmètre.")

    if est_metropole and df_region_dept is not None:
        st.markdown("**Rattachement à un département**")
        # department_coverage_summary renvoie des **parts**, pas des effectifs. Le
        # seuil à 0,5 % évite d'afficher « inconnu : 0 % », qui occupe une place
        # pour ne rien dire.
        couverture_dept = department_coverage_summary(df_region_dept)
        st.caption(
            "Origine du rattachement : "
            + " · ".join(f"{source} : {part:.0%}" for source, part in couverture_dept.items() if part >= 0.005)
            + ". La colonne « Département de l'opération » est peu renseignée sur cette "
            "période : l'essentiel du rattachement est **approché** depuis le code postal du "
            "bénéficiaire, puis depuis son nom — le siège du bénéficiaire, donc, et pas "
            "nécessairement le lieu du projet."
        )

# ---------------------------------------------------------------- Analyses

# Deux onglets, et non les trois des pages 2021-2027 : leur onglet « Pilotage »
# compare l'engagé au programmé de l'Accord de partenariat, qui n'existe pas
# encore pour cette période (#79). Un onglet vide vaudrait moins que pas d'onglet.
tab_ensemble, tab_audit = st.tabs(["Vue d'ensemble", "Analyses & contrôle"])

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
        # Aucun `totaux_programme` : pas d'enveloppe programmée connue pour la période,
        # donc pas de segment « reste à engager » ni de repère horizontal (#79).
        fig_fonds = build_fonds_barchart(df_fonds, FONDS_COLORS)
        fig_fonds.update_layout(height=400)
        st.plotly_chart(fig_fonds, use_container_width=True)
    with col_courbe:
        st.plotly_chart(build_cumulative_curve(df_ops, color_map=FONDS_COLORS), use_container_width=True)
        st.caption(
            "Montant UE programmé cumulé dans le temps, d'après la date de début de "
            "l'opération. Les programmations s'étalent jusqu'en 2023 : conventionnements "
            "tardifs et mobilisation de REACT-EU en fin de période. **La période d'une "
            "opération se lit à son fonds et à son programme, jamais à sa date.**"
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
            use_container_width=True,
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
        use_container_width=True,
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
        use_container_width=True,
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
            use_container_width=True,
        )
        st.caption("Échelle logarithmique : les montants s'étalent sur plusieurs ordres de grandeur.")
    with col_box:
        st.markdown("**Dispersion par fonds**")
        st.plotly_chart(build_boxplot(df_ops, FONDS, log_y=True, color_map=FONDS_COLORS), use_container_width=True)

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
        use_container_width=True,
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
        st.plotly_chart(build_pareto_beneficiaires(df_ops), use_container_width=True)
    with col_lorenz:
        st.plotly_chart(build_lorenz_beneficiaires(df_ops), use_container_width=True)

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
        use_container_width=True,
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
                use_container_width=True,
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
            use_container_width=True,
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
