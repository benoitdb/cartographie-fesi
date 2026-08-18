import pandas as pd
import streamlit as st

from utils.data_loader import (
    load_data,
    load_dromcom_codes_postaux,
    load_dromcom_geojson,
    load_programme_detail,
    load_programme_totals,
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
from utils.filters import FONDS_OPTIONS, render_fonds_filter, summarize_ops
from utils.pilotage import build_ranking_programme_vs_engage, build_trajectoire, render_kpi_pilotage
from utils.plot_style import MAP_CONFIG, build_standalone_colorbar
from utils.region_analysis import FONDS, render_region_audit, render_region_ensemble, render_region_gestion
from utils.table_style import text_widths
from utils.themes import FONDS_COLORS, OBJECTIF_STRATEGIQUE_COLORS, style_categorical_columns

st.set_page_config(page_title="Vue Régionale - Cartographie FESI", layout="wide")


@st.fragment
def render_liste_complete_projets(df_region_ops, region):
    # Toutes régions (métropole en plus du détail par département déjà affiché, DROM-COM
    # en l'absence de découpage départemental pertinent). Benchmarké sur Nouvelle-Aquitaine
    # (2510 opérations, la plus grosse région) le 2026-08-15 : construction du Styler ~0.05s,
    # rendu ~0.4s, filtrage recherche ~2ms — le tableau lui-même n'est pas un problème de
    # volume. Isolé en st.fragment pour que chaque frappe dans la recherche ne relance QUE ce
    # bloc, pas toute la page (treemaps, pilotage...) — sans ça, la saisie deviendrait
    # perceptiblement saccadée sur les grosses régions métropole.
    st.subheader("Liste complète des projets")

    recherche_projet = st.text_input(
        "Rechercher (intitulé du projet ou bénéficiaire)", key=f"recherche_projets_liste_complete_{region}"
    )
    df_projets = df_region_ops[
        [
            "Intitulé du projet",
            "Nom du bénéficiaire",
            FONDS,
            "Objectif stratégique",
            "Date première convention",
            "Montant UE",
        ]
    ].sort_values("Montant UE", ascending=False)
    if recherche_projet:
        masque_recherche = df_projets["Intitulé du projet"].str.contains(
            recherche_projet, case=False, na=False
        ) | df_projets["Nom du bénéficiaire"].str.contains(recherche_projet, case=False, na=False)
        df_projets = df_projets[masque_recherche]
    st.caption(f"{len(df_projets):,}".replace(",", " ") + f" / {len(df_region_ops):,}".replace(",", " ") + " projet(s).")

    st.dataframe(
        style_categorical_columns(df_projets, {FONDS: FONDS_COLORS, "Objectif stratégique": OBJECTIF_STRATEGIQUE_COLORS}),
        hide_index=True,
        use_container_width=True,
        column_config={
            **text_widths("Intitulé du projet", "Nom du bénéficiaire", "Objectif stratégique"),
            "Montant UE": st.column_config.ProgressColumn(
                format="%,d €",
                min_value=0,
                max_value=int(df_region_ops["Montant UE"].max()),
            ),
        },
    )

data = load_data()
by_region = data["aggregates"]["by_region"]
by_region_fonds = data["aggregates"]["by_region_fonds"]

selected_fonds = render_fonds_filter()
filtre_actif = set(selected_fonds) != set(FONDS_OPTIONS)

region = st.selectbox("Région", sorted(by_region))

st.title(f"Vue Régionale - {region}")

region_ops = [
    op
    for op in data["operations"]
    if op.get("regions_modernes") == [region]
    and not op.get("is_interregional")
    and not op.get("is_national")
    and op.get("Fonds") in selected_fonds
]

if not region_ops:
    st.info("Aucune opération pour cette région avec les fonds sélectionnés.")
    st.stop()

# Aperçu général : infos de base (une case, 4 lignes) à côté de la carte — carte des
# départements en métropole (calculée ici, réutilisée plus bas dans "Détail par département"
# plutôt que reconstruite deux fois), contour réel du territoire pour un DROM-COM (chaque
# DROM-COM correspond à un département/collectivité unique, pas de découpage pertinent en
# dessous, donc pas de "Détail par département" pour ces régions).
region_meta = load_region_metadata().get(region)
est_metropole = region in DEPT_TO_REGION.values()
df_region_dept = assign_departments_df(pd.DataFrame(region_ops)) if est_metropole else None

if not est_metropole:
    bubbles_df, couverture_localisation = build_bubbles_localisation(region_ops, region, load_dromcom_codes_postaux())
    total_localisation = sum(couverture_localisation.values())

apercu_col1, apercu_col2 = st.columns([1, 2])
with apercu_col1:
    if region_meta:
        categorie_affichee = region_meta["categorie_ue"] or "Non classifiée"
        if region_meta.get("ultraperipherique"):
            categorie_affichee += " + RUP"
        with st.container(border=True):
            population_fmt = f"{region_meta['population']:,}".replace(",", " ")
            st.markdown(f"**Population :** {population_fmt} ({region_meta['population_year']})")
            superficie_fmt = f"{region_meta['superficie_km2']:,.0f}".replace(",", " ")
            st.markdown(f"**Superficie :** {superficie_fmt} km²")
            st.markdown(f"**Chef-lieu :** {region_meta['chef_lieu']}")
            st.markdown(f"**Catégorie UE :** {categorie_affichee}")

        caption_categorie = (
            "Catégorie de région au sens de la politique de cohésion européenne 2021-2027 "
            "(PIB/habitant vs. moyenne UE) : détermine le taux de cofinancement FEDER/FSE+ "
            "applicable (jusqu'à 85% en région moins développée, 60% en transition, 50% en "
            "région plus développée). Source : décision d'exécution (UE) 2021/1130."
        )
        if region_meta.get("ultraperipherique"):
            caption_categorie += (
                " RUP : région ultrapériphérique — bénéficie en plus d'une allocation "
                "additionnelle (art. 349 TFUE) compensant un handicap structurel permanent, "
                "distincte de la catégorie de cohésion. Source : Accord de partenariat "
                "2021-2027, Tableau 9B."
            )
        st.caption(caption_categorie)
with apercu_col2:
    if est_metropole:
        st.plotly_chart(build_department_choropleth(df_region_dept, region), use_container_width=True, config=MAP_CONFIG)
    elif total_localisation:
        st.plotly_chart(
            build_dromcom_projects_map(region, load_dromcom_geojson(), bubbles_df), use_container_width=True, config=MAP_CONFIG
        )
        st.caption(
            f"{couverture_localisation['opération'] / total_localisation:.0%} localisées via le code "
            "postal de l'opération elle-même (fiable), "
            f"{couverture_localisation['bénéficiaire (approximé)'] / total_localisation:.0%} approximées "
            "via le code postal du bénéficiaire (siège du porteur de projet, pas nécessairement le lieu "
            "de réalisation du projet), "
            f"{couverture_localisation['non localisable'] / total_localisation:.0%} non localisables. "
            "Une bulle regroupe les opérations d'un même code postal, taille proportionnelle au montant "
            "UE cumulé."
        )
    else:
        st.plotly_chart(
            build_dromcom_outline(region, load_dromcom_geojson()), use_container_width=True, config=MAP_CONFIG
        )
        st.info("Aucune opération localisable pour cette région avec les fonds sélectionnés.")

if filtre_actif:
    region_data = summarize_ops(region_ops)
else:
    # Fonds par défaut (tous sélectionnés) : agrégat pré-calculé du pipeline, comportement inchangé
    region_data = by_region[region]

if region_meta:
    col1, col2, col3, col4 = st.columns(4)
else:
    col1, col2, col3 = st.columns(3)
with col1:
    with st.container(border=True):
        st.markdown(f"**Montant UE total :** {region_data['montant_ue_total'] / 1e6:,.1f} M€".replace(",", " "))
with col2:
    with st.container(border=True):
        st.markdown(f"**Nombre de projets :** {region_data['count']:,}".replace(",", " "))
with col3:
    with st.container(border=True):
        st.markdown(f"**Montant UE moyen :** {region_data['montant_ue_moyen'] / 1e3:,.0f} k€".replace(",", " "))
if region_meta:
    montant_par_habitant = region_data["montant_ue_total"] / region_meta["population"]
    with col4:
        with st.container(border=True):
            st.markdown(f"**Montant UE / habitant :** {montant_par_habitant:,.0f} €".replace(",", " "))

if filtre_actif:
    fonds_breakdown_df = None
else:
    # Fonds par défaut (tous sélectionnés) : agrégat pré-calculé du pipeline, comportement inchangé
    fonds_breakdown_df = pd.DataFrame(
        [
            {"fonds": v["fonds"], "montant_ue_total": v["montant_ue_total"], "count": v["count"]}
            for key, v in by_region_fonds.items()
            if v["region"] == region and v["fonds"] in selected_fonds
        ]
    ).sort_values("montant_ue_total")

programme_totals_region = load_programme_totals().get(region, {})
montant_programme_region = sum(v for f, v in programme_totals_region.items() if f in selected_fonds)
programme_totals_region_selection = {f: v for f, v in programme_totals_region.items() if f in selected_fonds}

tab_ensemble, tab_pilotage, tab_audit = st.tabs(["Vue d'ensemble", "Pilotage", "Analyses & contrôle"])

with tab_ensemble:
    df_region_ops = render_region_ensemble(
        region_ops,
        region,
        fonds_breakdown_df=fonds_breakdown_df,
        programme_totals=programme_totals_region_selection,
    )

    # Détail par département (régions métropole uniquement : les régions DROM
    # correspondent chacune à un département unique, pas de découpage pertinent)
    if region in DEPT_TO_REGION.values():
        st.subheader("Détail par département")

        df_region_dept = assign_departments_df(df_region_ops)
        coverage = department_coverage_summary(df_region_dept)

        depts_region = {code for code, r in DEPT_TO_REGION.items() if r == region}
        hors_region = df_region_dept["dept"].notna() & ~df_region_dept["dept"].isin(depts_region)
        part_hors_region = hors_region.sum() / len(df_region_dept) if len(df_region_dept) else 0

        st.caption(
            f"Rattachement département : {coverage['opération']:.0%} via la donnée pipeline (fiable), "
            f"{coverage['approximé']:.0%} approximé via le code postal du bénéficiaire (siège du "
            f"bénéficiaire, pas nécessairement le lieu de réalisation du projet), "
            f"{coverage['nom du bénéficiaire']:.0%} déduit du nom du bénéficiaire (mention explicite "
            f"d'une ville ou du département), {coverage['inconnu']:.0%} non rattaché (absent de la "
            "carte, faute de département identifié, mais comptabilisé dans le tableau ci-dessous). "
            f"{part_hors_region:.0%} des opérations pointent vers un département situé hors de {region} — "
            "voir la section dédiée plus bas ; elles restent comptées dans les totaux de la région "
            "(Fonds, objectifs, courbe...) puisque leur rattachement régional reste fiable, seul le "
            "département est en cause."
        )
        if region == "Corse":
            st.caption(
                "⚠️ Point de vigilance spécifique à la Corse : l'approximation par code postal du "
                "bénéficiaire ne s'applique pas ici (un code postal débutant par 20 ne permet pas de "
                "distinguer 2A/2B), d'où un recours plus fréquent à la déduction par nom du bénéficiaire "
                "et une part de données non rattachées plus élevée que dans les autres régions."
            )

        non_reparti = df_region_dept[df_region_dept["dept"].isna()]
        non_reparti_montant = non_reparti["Montant UE"].sum()
        non_reparti_count = len(non_reparti)

        df_dept_connu = df_region_dept[df_region_dept["dept"].notna() & df_region_dept["dept"].isin(depts_region)]
        dept_table = (
            df_dept_connu.groupby("dept")
            .agg(montant_ue_total=("Montant UE", "sum"), count=("Montant UE", "count"))
            .reset_index()
            .rename(columns={"dept": "Département", "montant_ue_total": "Montant UE total", "count": "Nb projets"})
            .sort_values("Montant UE total", ascending=False)
        )
        # Échelle calée sur les seuls départements (avant l'ajout de la ligne "Non réparti" ci-dessous,
        # qui ne correspond à aucun département sur la carte) — même échelle que la carte donc.
        color_range_dept = [0, dept_table["Montant UE total"].max()] if len(dept_table) else [0, 1]
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

        # Légende + carte + tableau côte à côte (plutôt qu'empilés) : la carte d'une seule région est
        # étroite, ce qui générait beaucoup de vide autour d'elle et du tableau en dessous. Même
        # principe de légende autonome que la carte nationale (Accueil.py) : la carte désactive son
        # colorbar intégré au profit d'une légende commune dans sa propre colonne.
        col_legend_dept, col_map_dept, col_table_dept = st.columns([1, 4, 5])
        with col_legend_dept:
            st.plotly_chart(
                build_standalone_colorbar(color_range_dept, "Montant UE (€)", height=420),
                use_container_width=True,
                config={"displayModeBar": False},
            )
        with col_map_dept:
            st.plotly_chart(
                build_department_choropleth(df_region_dept, region, show_colorbar=False),
                use_container_width=True,
                config=MAP_CONFIG,
            )
        with col_table_dept:
            st.dataframe(
                dept_table,
                hide_index=True,
                use_container_width=True,
                column_config={
                    **text_widths("Département"),
                    "Montant UE total": st.column_config.ProgressColumn(
                        format="%,d €",
                        min_value=0,
                        max_value=int(dept_table["Montant UE total"].max()) if len(dept_table) else 1,
                    ),
                },
            )

        if non_reparti_count:
            kpi_col1, kpi_col2 = st.columns(2)
            kpi_col1.metric("Montant non rattaché à un département", f"{non_reparti_montant / 1e6:,.2f} M€".replace(",", " "))
            kpi_col2.metric("Opérations non rattachées", f"{non_reparti_count}")

        # Opérations dont le département assigné sort du périmètre de la région
        st.subheader("Opérations rattachées à un département hors de la région")
        st.caption(
            f"Ces opérations sont bien attribuées à {region} (donnée fiable), mais leur département "
            "assigné (donnée pipeline ou approximation via le code postal du bénéficiaire) appartient à "
            "une autre région — le plus souvent parce que le siège du bénéficiaire est situé ailleurs "
            "que le lieu de réalisation du projet. Elles sont incluses dans tous les totaux de la région "
            "affichés sur cette page, mais exclues de la carte et du tableau ci-dessus."
        )

        df_hors_region = df_region_dept[hors_region].copy()
        df_hors_region["Région du département"] = df_hors_region["dept"].map(DEPT_TO_REGION)
        st.caption(f"{len(df_hors_region)} opération(s) concernée(s).")
        df_hors_region_table = (
            df_hors_region[
                ["Intitulé du projet", "Nom du bénéficiaire", FONDS, "dept", "Région du département", "dept_source", "Montant UE"]
            ].rename(columns={"dept": "Département", "dept_source": "Rattachement"}).sort_values("Montant UE", ascending=False)
        )
        st.dataframe(
            style_categorical_columns(df_hors_region_table, {FONDS: FONDS_COLORS}),
            hide_index=True,
            use_container_width=True,
            column_config={
                **text_widths("Intitulé du projet", "Nom du bénéficiaire", "Département", "Région du département", "Rattachement"),
                "Montant UE": st.column_config.ProgressColumn(
                    format="%,d €",
                    min_value=0,
                    max_value=int(df_hors_region_table["Montant UE"].max()) if len(df_hors_region_table) else 1,
                ),
            },
        )

    render_liste_complete_projets(df_region_ops, region)

    # Opérations interrégionales impliquant cette région — pour info uniquement, exclues de tous
    # les totaux/graphes ci-dessus (comme partout ailleurs dans le dashboard, is_interregional est
    # filtré des vues par région, voir filters.py). Concerne 6 régions au total : Auvergne-Rhône-
    # Alpes, Bourgogne-Franche-Comté, Grand Est, Île-de-France, Occitanie, Provence-Alpes-Côte
    # d'Azur — surtout des actions "massif"/"fleuve" (Rhône-Saône, massif des Alpes) à cheval sur
    # plusieurs régions au sein d'un même programme régional (voir issue #19, à ne pas confondre
    # avec Interreg).
    ops_interregionaux_region = [
        op
        for op in data["operations"]
        if op.get("is_interregional") and op.get("Fonds") in selected_fonds and region in (op.get("regions_modernes") or [])
    ]
    if ops_interregionaux_region:
        st.subheader("Opérations interrégionales impliquant cette région")
        st.caption(
            f"{len(ops_interregionaux_region)} opération(s) dont le territoire couvre plusieurs régions à la "
            "fois, dont celle-ci — pour information uniquement, non comptées dans les totaux et graphes "
            "ci-dessus (déjà comptabilisées une fois au niveau national, voir Accueil)."
        )
        df_interregionaux_region = pd.DataFrame(ops_interregionaux_region)
        df_interregionaux_region["Autres régions"] = df_interregionaux_region["regions_modernes"].apply(
            lambda regions: ", ".join(r for r in regions if r != region)
        )
        df_interregionaux_table = df_interregionaux_region[
            ["Intitulé du projet", "Nom du bénéficiaire", FONDS, "Autres régions", "Montant UE"]
        ].sort_values("Montant UE", ascending=False)
        st.dataframe(
            style_categorical_columns(df_interregionaux_table, {FONDS: FONDS_COLORS}),
            hide_index=True,
            use_container_width=True,
            column_config={
                **text_widths("Intitulé du projet", "Nom du bénéficiaire", "Autres régions"),
                "Montant UE": st.column_config.ProgressColumn(
                    format="%,d €",
                    min_value=0,
                    max_value=int(df_interregionaux_table["Montant UE"].max()),
                ),
            },
        )

with tab_pilotage:
    # Pilotage : programmé (Tableau 9B, Accord de partenariat 2021-2027) vs engagé (data.json)
    st.subheader("Pilotage : programmé vs engagé")

    if montant_programme_region:
        engage_by_fonds = pd.DataFrame(region_ops).groupby("Fonds")["Montant UE"].sum().to_dict()
        df_fonds_pilotage = pd.DataFrame(
            [
                {"fonds": f, "engage": engage_by_fonds.get(f, 0), "programme": programme_totals_region[f]}
                for f in ("FEDER", "FSE+", "FTJ")
                if f in programme_totals_region
            ]
        )
        programme_detail = load_programme_detail()
        render_kpi_pilotage(
            df_fonds_pilotage,
            montant_programme_region,
            region_data["montant_ue_total"],
            ftj_article=programme_detail["ftj_article"].get(region) if "FTJ" in selected_fonds else None,
            assistance_technique={
                f: v for f, v in programme_detail["assistance_technique"].get(region, {}).items() if f in selected_fonds
            },
        )

        # Allocation additionnelle ultrapériphérique (RUP, art. 349 TFUE) : distincte de la
        # dotation de catégorie de région de base, jusqu'ici fusionnée dans programme_totals_region
        # sans être exposée séparément (voir data-pipeline/programme_totals.py, clé "rup").
        rup_region = programme_detail.get("rup", {}).get(region, {})
        if region_meta and region_meta.get("ultraperipherique") and rup_region:
            with st.expander(f"ℹ️ Allocation additionnelle ultrapériphérique (RUP) pour {region}"):
                st.caption(
                    f"En tant que région ultrapériphérique (art. 349 TFUE), {region} bénéficie d'une "
                    "allocation additionnelle, en plus de sa dotation de catégorie de région de base, "
                    "destinée à compenser un handicap structurel permanent (éloignement, insularité, "
                    "relief, climat, dépendance économique à un petit nombre de produits — Accord de "
                    "partenariat 2021-2027, Tableau 9B)."
                )
                rup_rows = [
                    {
                        "Fonds": f,
                        "Dotation catégorie de base": programme_totals_region.get(f, 0) - montant_rup,
                        "Allocation RUP additionnelle": montant_rup,
                        "Total programmé": programme_totals_region.get(f, 0),
                    }
                    for f, montant_rup in rup_region.items()
                    if f in selected_fonds
                ]
                if rup_rows:
                    st.dataframe(
                        pd.DataFrame(rup_rows),
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            col: st.column_config.NumberColumn(format="%,d €")
                            for col in ("Dotation catégorie de base", "Allocation RUP additionnelle", "Total programmé")
                        },
                    )
                else:
                    st.caption("Aucune allocation RUP pour les fonds actuellement sélectionnés.")

        traj_col, bullet_col = st.columns(2)
        with traj_col:
            st.plotly_chart(build_trajectoire(pd.DataFrame(region_ops), montant_programme_region), use_container_width=True)
        with bullet_col:
            if not df_fonds_pilotage.empty:
                st.plotly_chart(
                    build_ranking_programme_vs_engage(df_fonds_pilotage, "fonds", "engage", "programme", height=400),
                    use_container_width=True,
                )
    else:
        st.info("Pas de donnée programmée (Tableau 9B) pour cette région avec les fonds sélectionnés.")

    render_region_gestion(df_region_ops, region)

    st.caption(
        "Fonction comptable (certification) : depuis 2021-2027, cette fonction est intégrée à "
        "l'Autorité de gestion (règlement (UE) 2021/1060, art. 76) — il n'y a plus d'autorité de "
        "certification distincte comme sur 2014-2020, donc pas d'espace séparé pour elle ici."
    )

with tab_audit:
    render_region_audit(df_region_ops, region, region_meta=region_meta)
