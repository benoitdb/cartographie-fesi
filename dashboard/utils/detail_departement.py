"""« Détail par département » d'une région métropolitaine, partagé entre la Vue Régionale
(2021-2027) et la page 2014-2020 (issue #157, écart D3).

Les deux pages avaient divergé : la page 1 listait les opérations rattachées hors de la
région dans une section dédiée, la page 5 les résumait par une ligne « Hors périmètre »
dans le tableau (#100). Arbitrage : les deux, sur les deux pages — la ligne pour que le
tableau totalise la région, la liste pour savoir de quelles opérations il s'agit.

Restent propres à chaque page : le titre et les légendes sur l'origine du rattachement
(les sources ne pèsent pas pareil d'une période à l'autre), la mise en garde Corse et
l'annotation de carte.
"""

import streamlit as st

from utils.departments import DEPT_TO_REGION, build_department_choropleth, tableau_departements
from utils.plot_style import MAP_CONFIG, build_standalone_colorbar
from utils.table_style import text_widths
from utils.themes import FONDS_COLORS, style_categorical_columns

FONDS = "Fonds"


def render_detail_departement(df_dept, region, annotation=None, metriques_non_reparti=False):
    """Légende, carte et tableau côte à côte, puis la liste des opérations rattachées à un
    département d'une autre région.

    `df_dept` : opérations de la région passées par `assign_departments_df`.
    `metriques_non_reparti` : deux indicateurs sous le tableau (montant et nombre
    d'opérations sans département), affichés par la Vue Régionale."""
    tableau, color_range = tableau_departements(df_dept, region)

    # Légende + carte + tableau côte à côte (plutôt qu'empilés) : la carte d'une seule région
    # est étroite. Même principe de légende autonome que la carte nationale : la carte
    # désactive son colorbar au profit d'une légende commune dans sa propre colonne.
    col_legend, col_map, col_table = st.columns([1, 4, 5])
    with col_legend:
        st.plotly_chart(
            build_standalone_colorbar(color_range, "Montant UE (€)", height=420),
            width='stretch',
            config={"displayModeBar": False},
        )
    with col_map:
        st.plotly_chart(
            build_department_choropleth(df_dept, region, show_colorbar=False, annotation=annotation),
            width='stretch',
            config=MAP_CONFIG,
        )
    with col_table:
        st.dataframe(
            tableau,
            hide_index=True,
            width='stretch',
            column_config={
                **text_widths("Département"),
                "Montant UE total": st.column_config.ProgressColumn(
                    format="%,d €",
                    min_value=0,
                    max_value=int(tableau["Montant UE total"].max()) if len(tableau) else 1,
                ),
            },
        )

    non_reparti = df_dept[df_dept["dept"].isna()]
    if metriques_non_reparti and len(non_reparti):
        kpi_col1, kpi_col2 = st.columns(2)
        kpi_col1.metric(
            "Montant non rattaché à un département", f"{non_reparti['Montant UE'].sum() / 1e6:,.2f} M€".replace(",", " ")
        )
        kpi_col2.metric("Opérations non rattachées", f"{len(non_reparti)}")

    depts_region = {code for code, r in DEPT_TO_REGION.items() if r == region}
    hors_region = df_dept["dept"].notna() & ~df_dept["dept"].isin(depts_region)
    st.subheader("Opérations rattachées à un département hors de la région")
    st.caption(
        f"Ces opérations sont bien attribuées à {region} (donnée fiable), mais leur département "
        "assigné appartient à une autre région — soit un projet réalisé hors de "
        f"{region} par un porteur qui y a son siège, soit, pour les cas approchés, le siège du "
        "bénéficiaire situé ailleurs que le lieu de réalisation du projet. Elles sont incluses dans "
        "tous les totaux de la région affichés sur cette page, absentes de la carte, et regroupées "
        "dans la ligne « Hors périmètre » du tableau ci-dessus."
    )
    df_hors_region = df_dept[hors_region].copy()
    df_hors_region["Région du département"] = df_hors_region["dept"].map(DEPT_TO_REGION)
    st.caption(f"{len(df_hors_region)} opération(s) concernée(s).")
    table_hors_region = (
        df_hors_region[
            ["Intitulé du projet", "Nom du bénéficiaire", FONDS, "dept", "Région du département", "dept_source", "Montant UE"]
        ]
        .rename(columns={"dept": "Département", "dept_source": "Rattachement"})
        .sort_values("Montant UE", ascending=False)
    )
    st.dataframe(
        style_categorical_columns(table_hors_region, {FONDS: FONDS_COLORS}),
        hide_index=True,
        width='stretch',
        column_config={
            **text_widths("Intitulé du projet", "Nom du bénéficiaire", "Département", "Région du département", "Rattachement"),
            "Montant UE": st.column_config.ProgressColumn(
                format="%,d €",
                min_value=0,
                max_value=int(table_hors_region["Montant UE"].max()) if len(table_hors_region) else 1,
            ),
        },
    )
