import pandas as pd
import plotly.express as px
import streamlit as st

from utils.data_loader import load_data
from utils.departments import DEPT_TO_REGION, assign_departments_df, build_department_choropleth, department_coverage_summary
from utils.filters import FONDS_OPTIONS, render_fonds_filter, summarize_ops
from utils.stats import (
    build_boxplot,
    build_histogram,
    build_portfolio_scatter,
    compute_cofinancement_table,
    compute_stats_table,
    detect_cofinancement_outliers,
    detect_outliers,
)
from utils.treemap import build_hierarchy_treemap

FONDS, LEVEL1, LEVEL2, LEVEL3 = "Fonds", "Objectif stratégique", "Objectif spécifique (Code et libellé)", "Type d'intervention"

st.set_page_config(page_title="Vue Régionale - Cartographie FESI", layout="wide")

data = load_data()
by_region = data["aggregates"]["by_region"]
by_region_fonds = data["aggregates"]["by_region_fonds"]

selected_fonds = render_fonds_filter()
filtre_actif = set(selected_fonds) != set(FONDS_OPTIONS)

# "Volet national" n'est pas une région géographique : listé à part, en fin de sélecteur
regions = sorted(r for r in by_region if r != "Volet national") + ["Volet national"]

region = st.selectbox("Région", regions)

st.title(f"Vue Régionale - {region}")

if region == "Volet national":
    region_ops = [op for op in data["operations"] if op.get("is_national") and op.get("Fonds") in selected_fonds]
else:
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

if filtre_actif:
    region_data = summarize_ops(region_ops)
else:
    # Fonds par défaut (tous sélectionnés) : agrégat pré-calculé du pipeline, comportement inchangé
    region_data = by_region[region]

col1, col2, col3 = st.columns(3)
col1.metric("Montant UE total", f"{region_data['montant_ue_total'] / 1e6:,.1f} M€".replace(",", " "))
col2.metric("Nombre de projets", f"{region_data['count']:,}".replace(",", " "))
col3.metric("Montant UE moyen", f"{region_data['montant_ue_moyen'] / 1e3:,.0f} k€".replace(",", " "))

# Répartition par fonds
st.subheader("Répartition par fonds")

df_region_fonds = pd.DataFrame(
    [
        {"fonds": v["fonds"], "montant_ue_total": v["montant_ue_total"], "count": v["count"]}
        for key, v in by_region_fonds.items()
        if v["region"] == region and v["fonds"] in selected_fonds
    ]
).sort_values("montant_ue_total")

fig_region_fonds = px.bar(
    df_region_fonds,
    x="montant_ue_total",
    y="fonds",
    orientation="h",
    color="fonds",
    hover_data=["count"],
    labels={"montant_ue_total": "Montant UE (€)", "fonds": "Fonds", "count": "Nb projets"},
)
fig_region_fonds.update_layout(height=250, showlegend=False)
fig_region_fonds.update_traces(width=0.5)

st.plotly_chart(fig_region_fonds, use_container_width=True)

df_region_ops = pd.DataFrame(region_ops)
df_region_ops[LEVEL1] = df_region_ops[LEVEL1].fillna("Non spécifié")
df_region_ops[LEVEL2] = df_region_ops[LEVEL2].fillna("Non spécifié")
df_region_ops[LEVEL3] = df_region_ops[LEVEL3].fillna("Non spécifié")

# Vue d'ensemble : fonds > objectif stratégique > objectif spécifique
st.subheader("Fonds, objectifs stratégiques et spécifiques")

fig_hierarchy = build_hierarchy_treemap(df_region_ops, [FONDS, LEVEL1, LEVEL2])

st.plotly_chart(fig_hierarchy, use_container_width=True)

# Détail par fonds : objectif stratégique > spécifique > type d'intervention
st.subheader("Détail par fonds")

fonds_presents = sorted(df_region_ops[FONDS].unique())
fonds_cols = st.columns(len(fonds_presents))

for col, fonds in zip(fonds_cols, fonds_presents):
    with col:
        st.markdown(f"**{fonds}**")
        df_fonds = df_region_ops[df_region_ops[FONDS] == fonds]
        fig_fonds_detail = build_hierarchy_treemap(df_fonds, [LEVEL1, LEVEL2, LEVEL3])
        st.plotly_chart(fig_fonds_detail, use_container_width=True)

# Analyses statistiques
st.subheader("Analyses statistiques")
st.caption(
    "Ces indicateurs complètent les agrégats de base (somme, moyenne) affichés plus haut : ils "
    "renseignent sur la dispersion des montants, la concentration du portefeuille et la cohérence "
    "des taux de cofinancement — des repères usuels pour l'analyse de dépense publique."
)

st.caption(
    f"Distribution des montants UE par opération, pour {region}. Ces montants sont très "
    "asymétriques (majorité de petites opérations, quelques grands projets) : l'échelle "
    "logarithmique rend la forme de la distribution plus lisible."
)
echelle_hist = st.radio("Échelle", ["Logarithmique", "Linéaire"], horizontal=True, key="echelle_hist_regionale")
st.plotly_chart(
    build_histogram(df_region_ops, log_x=echelle_hist == "Logarithmique", color_col=FONDS),
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
    "portée par les 10% de projets les plus importants du groupe."
)

st.markdown("**Médiane, écart-type et concentration par fonds**")
stats_fonds_region = compute_stats_table(df_region_ops, FONDS).rename(
    columns={"mediane": "Médiane", "ecart_type": "Écart-type", "count": "Nb projets"}
)
st.dataframe(stats_fonds_region, hide_index=True, use_container_width=True, column_config=stats_col_config)

st.markdown("**Visualisation (boîtes à moustaches)**")
st.caption(
    "Chaque boîte représente la médiane et l'écart interquartile (IQR) du groupe ; les points "
    "au-delà des moustaches sont les opérations à montant atypique."
)
echelle_box_region = st.radio("Échelle ", ["Logarithmique", "Linéaire"], horizontal=True, key="echelle_box_regionale")
box_col_fonds_region, box_col_objectif_region = st.columns(2)
with box_col_fonds_region:
    st.plotly_chart(
        build_boxplot(df_region_ops, FONDS, log_y=echelle_box_region == "Logarithmique"), use_container_width=True
    )
with box_col_objectif_region:
    st.plotly_chart(
        build_boxplot(df_region_ops, LEVEL1, log_y=echelle_box_region == "Logarithmique"), use_container_width=True
    )

st.markdown("**Opérations à montant atypique**")
st.caption(
    "Opérations dont le montant s'écarte fortement de la distribution habituelle du groupe "
    "(méthode IQR) — à examiner, sans présumer d'une anomalie : un montant élevé peut aussi "
    "correspondre à un projet structurant légitime."
)
outliers_region = detect_outliers(df_region_ops)
st.caption(f"{len(outliers_region)} opération(s) hors de l'intervalle interquartile habituel.")
st.dataframe(
    outliers_region[["Intitulé du projet", "Nom du bénéficiaire", FONDS, "Montant UE"]].head(50),
    hide_index=True,
    use_container_width=True,
    column_config={"Montant UE": montant_col_config},
)

st.markdown("**Structure du portefeuille par type d'intervention**")
st.caption(
    "Nombre de projets (x) vs montant UE moyen (y), taille de bulle = montant UE total : distingue "
    "les types d'intervention portés par peu de gros projets (souvent infrastructure) de ceux portés "
    "par de nombreux petits projets (souvent formation, aides individuelles)."
)
st.plotly_chart(build_portfolio_scatter(df_region_ops, LEVEL3), use_container_width=True)

st.markdown("**Taux de cofinancement UE**")
st.caption(
    "Le taux de cofinancement est plafonné réglementairement selon le fonds et la catégorie de région "
    "(plafonds non modélisés ici) ; un taux atypique peut signaler une opération à vérifier."
)
taux_col_config = st.column_config.NumberColumn(format="percent")
cofinancement_fonds_region = compute_cofinancement_table(df_region_ops, FONDS).rename(
    columns={"taux_moyen": "Taux moyen", "taux_median": "Taux médian", "count": "Nb projets"}
)
st.dataframe(
    cofinancement_fonds_region,
    hide_index=True,
    use_container_width=True,
    column_config={"Taux moyen": taux_col_config, "Taux médian": taux_col_config},
)

cofinancement_outliers_region = detect_cofinancement_outliers(df_region_ops)
st.caption(f"{len(cofinancement_outliers_region)} opération(s) à taux de cofinancement atypique (méthode IQR).")
st.dataframe(
    cofinancement_outliers_region[["Intitulé du projet", FONDS, "Taux de cofinancement"]].head(50),
    hide_index=True,
    use_container_width=True,
    column_config={"Taux de cofinancement": taux_col_config},
)

# Courbe cumulée d'engagement UE dans le temps
st.subheader("Engagement UE cumulé dans le temps")
st.caption(
    "Basé sur la date de début de l'opération. Environ 60% des dates sont arrondies au 1ᵉʳ janvier "
    "(date administrative/programmatique plutôt qu'une date de démarrage individuelle précise) : "
    "la courbe présente donc des paliers plutôt qu'une progression lissée."
)

st.caption("Cliquer sur un fonds dans la légende pour l'isoler ou le masquer.")

df_dates = df_region_ops[["Date de début de l'opération", "Montant UE", "Fonds"]].copy()
df_dates["Date de début de l'opération"] = pd.to_datetime(df_dates["Date de début de l'opération"])
df_dates = (
    df_dates.groupby(["Fonds", "Date de début de l'opération"], as_index=False)["Montant UE"]
    .sum()
    .sort_values(["Fonds", "Date de début de l'opération"])
)
df_dates["cumule"] = df_dates.groupby("Fonds")["Montant UE"].cumsum()

fig_cumul = px.line(
    df_dates,
    x="Date de début de l'opération",
    y="cumule",
    color="Fonds",
    labels={"Date de début de l'opération": "Date", "cumule": "Montant UE cumulé (€)"},
)
fig_cumul.update_traces(line=dict(width=2))

for year in range(
    df_dates["Date de début de l'opération"].dt.year.min(), df_dates["Date de début de l'opération"].dt.year.max() + 1
):
    fig_cumul.add_vline(x=f"{year}-01-01", line_dash="dot", line_color="gray", opacity=0.4)

st.plotly_chart(fig_cumul, use_container_width=True)

# Détail par département (régions métropole uniquement : les régions DOM-TOM
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
        f"{coverage['inconnu']:.0%} non rattaché (exclu de la carte et du tableau ci-dessous). "
        f"{part_hors_region:.0%} des opérations pointent vers un département situé hors de {region} — "
        "voir la section dédiée plus bas ; elles restent comptées dans les totaux de la région "
        "(Fonds, objectifs, courbe...) puisque leur rattachement régional reste fiable, seul le "
        "département est en cause."
    )

    st.plotly_chart(build_department_choropleth(df_region_dept, region), use_container_width=True)

    df_dept_connu = df_region_dept[df_region_dept["dept"].notna() & df_region_dept["dept"].isin(depts_region)]
    dept_table = (
        df_dept_connu.groupby("dept")
        .agg(montant_ue_total=("Montant UE", "sum"), count=("Montant UE", "count"))
        .reset_index()
        .rename(columns={"dept": "Département", "montant_ue_total": "Montant UE total", "count": "Nb projets"})
        .sort_values("Montant UE total", ascending=False)
    )
    st.dataframe(
        dept_table,
        hide_index=True,
        use_container_width=True,
        column_config={"Montant UE total": st.column_config.NumberColumn(format="%d €")},
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
        column_config={"Montant UE": st.column_config.NumberColumn(format="%d €")},
    )
