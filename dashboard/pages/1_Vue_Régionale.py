import pandas as pd
import streamlit as st

from utils.data_loader import load_data, load_programme_totals, load_region_metadata
from utils.departments import DEPT_TO_REGION, assign_departments_df, build_department_choropleth, department_coverage_summary
from utils.filters import FONDS_OPTIONS, render_fonds_filter, summarize_ops
from utils.pilotage import build_ranking_programme_vs_engage, build_trajectoire, render_kpi_pilotage
from utils.plot_style import MAP_CONFIG
from utils.region_analysis import FONDS, render_region_analysis

st.set_page_config(page_title="Vue Régionale - Cartographie FESI", layout="wide")

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

# Aperçu général : infos de base (une case, 4 lignes) à côté de la carte des départements
# (régions métropole uniquement : les régions DROM correspondent chacune à un département
# unique, pas de découpage pertinent). Carte calculée ici, réutilisée plus bas dans "Détail
# par département" plutôt que reconstruite deux fois.
region_meta = load_region_metadata().get(region)
est_metropole = region in DEPT_TO_REGION.values()
df_region_dept = assign_departments_df(pd.DataFrame(region_ops)) if est_metropole else None

apercu_col1, apercu_col2 = st.columns([1, 2]) if est_metropole else (st.columns(1)[0], None)
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
if est_metropole:
    with apercu_col2:
        st.plotly_chart(build_department_choropleth(df_region_dept, region), use_container_width=True, config=MAP_CONFIG)

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

# Pilotage : programmé (Tableau 9B, Accord de partenariat 2021-2027) vs engagé (data.json)
st.subheader("Pilotage : programmé vs engagé")
programme_totals_region = load_programme_totals().get(region, {})
montant_programme_region = sum(v for f, v in programme_totals_region.items() if f in selected_fonds)

if montant_programme_region:
    engage_by_fonds = pd.DataFrame(region_ops).groupby("Fonds")["Montant UE"].sum().to_dict()
    df_fonds_pilotage = pd.DataFrame(
        [
            {"fonds": f, "engage": engage_by_fonds.get(f, 0), "programme": programme_totals_region[f]}
            for f in ("FEDER", "FSE+", "FTJ")
            if f in programme_totals_region
        ]
    )
    render_kpi_pilotage(df_fonds_pilotage, montant_programme_region, region_data["montant_ue_total"])

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

df_region_ops = render_region_analysis(
    region_ops,
    region,
    fonds_breakdown_df=fonds_breakdown_df,
    programme_totals={f: v for f, v in programme_totals_region.items() if f in selected_fonds},
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
    if non_reparti_count:
        kpi_col1, kpi_col2 = st.columns(2)
        kpi_col1.metric("Montant non rattaché à un département", f"{non_reparti_montant / 1e6:,.2f} M€".replace(",", " "))
        kpi_col2.metric("Opérations non rattachées", f"{non_reparti_count}")

    st.plotly_chart(build_department_choropleth(df_region_dept, region), use_container_width=True)

    df_dept_connu = df_region_dept[df_region_dept["dept"].notna() & df_region_dept["dept"].isin(depts_region)]
    dept_table = (
        df_dept_connu.groupby("dept")
        .agg(montant_ue_total=("Montant UE", "sum"), count=("Montant UE", "count"))
        .reset_index()
        .rename(columns={"dept": "Département", "montant_ue_total": "Montant UE total", "count": "Nb projets"})
        .sort_values("Montant UE total", ascending=False)
    )
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
    st.dataframe(
        dept_table,
        hide_index=True,
        use_container_width=True,
        column_config={"Montant UE total": st.column_config.NumberColumn(format="%,d €")},
    )

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
    st.dataframe(
        df_hors_region[
            ["Intitulé du projet", "Nom du bénéficiaire", FONDS, "dept", "Région du département", "dept_source", "Montant UE"]
        ].rename(columns={"dept": "Département", "dept_source": "Rattachement"}).sort_values("Montant UE", ascending=False),
        hide_index=True,
        use_container_width=True,
        column_config={"Montant UE": st.column_config.NumberColumn(format="%,d €")},
    )
