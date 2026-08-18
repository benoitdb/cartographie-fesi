import pandas as pd
import plotly.express as px
import streamlit as st

from utils.plot_style import style_hover
from utils.stats import (
    build_boxplot,
    build_cumulative_curve,
    build_fonds_barchart,
    build_histogram,
    build_lorenz_beneficiaires,
    build_pareto_beneficiaires,
    build_portfolio_scatter_comparison,
    compute_cofinancement_table,
    compute_stats_table,
    detect_cofinancement_outliers,
    detect_incoherent_cofinancement,
    detect_outliers,
    detect_regroupements_beneficiaire,
    render_top_beneficiaires_drilldown,
)
from utils.themes import FONDS_COLORS, OBJECTIF_STRATEGIQUE_COLORS, style_categorical_columns
from utils.treemap import build_hierarchy_treemap

FONDS, LEVEL1, LEVEL2, LEVEL3 = "Fonds", "Objectif stratégique", "Objectif spécifique (Code et libellé)", "Type d'intervention"


def render_region_ensemble(region_ops, region_label, fonds_breakdown_df=None, key_suffix="", programme_totals=None):
    """Tronc commun : répartition par fonds, courbe cumulée, treemaps (vue d'ensemble et détail
    par fonds), structure du portefeuille par type d'intervention — description factuelle,
    aucune analyse de dispersion/atypie ici (voir render_region_audit). Partagé entre Vue
    Régionale et Volet National, appelé dans l'onglet "Vue d'ensemble" de chaque page.

    Construit et retourne df_region_ops (colonnes LEVEL1/LEVEL2/LEVEL3 nettoyées des NaN) :
    les onglets Pilotage et Analyses & contrôle le réutilisent tel quel, pas besoin de
    reconstruire ce DataFrame trois fois.

    fonds_breakdown_df : DataFrame précalculé (colonnes fonds/montant_ue_total/count) pour
    le graphe "Répartition par fonds", à la place du recalcul depuis region_ops — utilisé
    par Vue Régionale pour réutiliser l'agrégat pré-calculé du pipeline quand aucun filtre
    fonds n'est actif (comportement inchangé, léger gain de perf). None recalcule toujours.

    programme_totals : dict fonds -> montant programmé (Tableau 9B, cf. `pilotage.py`), pour
    tracer sur la courbe cumulée un repère horizontal par fonds au niveau de son enveloppe
    programmée — l'écart entre la courbe et ce repère est le reste à consommer. None si pas
    de donnée programmée pour ce périmètre (n'affiche alors aucun repère).

    key_suffix : rend uniques les clés des widgets Streamlit (st.radio) quand la fonction
    est appelée plusieurs fois dans la même session (une page par région/volet national,
    mais l'état des widgets est partagé entre pages via leur clé).
    """
    st.subheader("Répartition par fonds")

    if fonds_breakdown_df is not None:
        df_region_fonds = fonds_breakdown_df
    else:
        df_region_fonds = (
            pd.DataFrame(region_ops)
            .groupby("Fonds")
            .agg(montant_ue_total=("Montant UE", "sum"), count=("Montant UE", "count"))
            .reset_index()
            .rename(columns={"Fonds": "fonds"})
            .sort_values("montant_ue_total")
        )

    # Empilée avec un segment "Reste à engager" (programme_totals) quand disponible — le
    # sommet de chaque barre rejoint alors l'enveloppe programmée (issue #33bis).
    fig_region_fonds = build_fonds_barchart(df_region_fonds, FONDS_COLORS, totaux_programme=programme_totals)
    fig_region_fonds.update_layout(height=400)

    fonds_col, progress_col = st.columns([1, 3])
    with fonds_col:
        st.plotly_chart(fig_region_fonds, use_container_width=True)
    with progress_col:
        mode_courbe = st.radio("Courbe cumulée", ["Montant", "%"], horizontal=True, key=f"mode_courbe{key_suffix}")
        mode_courbe_val = "pourcentage" if mode_courbe == "%" else "montant"
        st.plotly_chart(
            build_cumulative_curve(pd.DataFrame(region_ops), color_map=FONDS_COLORS, totaux_ref=programme_totals, mode=mode_courbe_val),
            use_container_width=True,
        )
        st.caption(
            "Engagement UE cumulé dans le temps. Basé sur la date de début de l'opération — environ 60% "
            "des dates sont arrondies au 1ᵉʳ janvier (date administrative plutôt qu'une date de démarrage "
            "précise), d'où des paliers plutôt qu'une progression lissée. Cliquer sur un fonds dans la "
            "légende pour l'isoler ou le masquer. En mode %, seuls les fonds avec une enveloppe programmée "
            "connue sont affichés."
        )

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
            fig_fonds_detail = build_hierarchy_treemap(
                df_fonds, [LEVEL1, LEVEL2, LEVEL3], color_map=OBJECTIF_STRATEGIQUE_COLORS
            )
            st.plotly_chart(fig_fonds_detail, use_container_width=True)

    st.markdown("**Structure du portefeuille par type d'intervention**")
    st.caption(
        "Chaque bulle est une combinaison type d'intervention / objectif stratégique, positionnée par "
        "nombre de projets (x) et montant UE moyen ou total (y selon le graphique) — utile pour repérer "
        "si une thématique de financement (couleur) concentre l'essentiel de la valeur sur certains "
        "types d'intervention (souvent infrastructure) plutôt que sur de nombreux petits projets "
        "(souvent formation, aides individuelles)."
    )
    st.plotly_chart(
        build_portfolio_scatter_comparison(df_region_ops, LEVEL3, LEVEL1, color_map=OBJECTIF_STRATEGIQUE_COLORS),
        use_container_width=True,
    )

    return df_region_ops


def render_region_gestion(df_region_ops, region_label):
    """Espace Autorité de gestion : répartition engagé seul par Objectif Stratégique — le Tableau
    8 de l'Accord de partenariat (source du pilotage par Fonds, rendu séparément par les pages
    appelantes juste avant cet onglet) ne ventile les dotations programmées par OS qu'au niveau
    national, pas par région (voir issue #21, #28). Pas de dotation régionale par OS disponible
    à ce jour pour tracer un taux de consommation ici, donc engagé seul."""
    st.subheader("Répartition par Objectif Stratégique")
    df_region_os = (
        df_region_ops.groupby(LEVEL1).agg(montant_ue_total=("Montant UE", "sum"), count=("Montant UE", "count")).reset_index()
    )
    fig_region_os = px.bar(
        df_region_os,
        x=LEVEL1,
        y="montant_ue_total",
        color=LEVEL1,
        color_discrete_map=OBJECTIF_STRATEGIQUE_COLORS,
        hover_data=["count"],
        labels={"montant_ue_total": "Montant UE (€)", LEVEL1: "Objectif stratégique", "count": "Nb projets"},
    )
    fig_region_os.update_layout(height=400, showlegend=False, xaxis_title=None)
    fig_region_os.for_each_trace(
        lambda t: t.update(
            hovertemplate=f"<b>{t.name}</b><br>Montant UE : %{{y:,.0f}} €<br>Nb projets : %{{customdata[0]:,.0f}}<extra></extra>"
        )
    )
    st.plotly_chart(style_hover(fig_region_os), use_container_width=True)


def render_region_audit(df_region_ops, region_label, key_suffix=""):
    """Espace Autorité d'audit : dispersion/concentration des montants, opérations atypiques,
    regroupements par bénéficiaire (dont inter-fonds, #23), cofinancement atypique, cohérence
    des montants — indicateurs usuels de contrôle de dépense publique, pas de description
    structurelle (voir render_region_ensemble pour ça)."""
    st.caption(
        "Ces indicateurs complètent les agrégats de base (somme, moyenne) affichés dans la vue "
        "d'ensemble : ils renseignent sur la dispersion des montants, la concentration du "
        "portefeuille et la cohérence des taux de cofinancement — des repères usuels pour l'analyse "
        "de dépense publique."
    )

    st.caption(
        f"Distribution des montants UE par opération, pour {region_label}. Ces montants sont très "
        "asymétriques (majorité de petites opérations, quelques grands projets) : l'échelle "
        "logarithmique rend la forme de la distribution plus lisible."
    )
    echelle_hist = st.radio("Échelle", ["Logarithmique", "Linéaire"], horizontal=True, key=f"echelle_hist{key_suffix}")
    st.plotly_chart(
        build_histogram(df_region_ops, log_x=echelle_hist == "Logarithmique", color_col=FONDS, color_map=FONDS_COLORS),
        use_container_width=True,
    )

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
    st.dataframe(
        style_categorical_columns(stats_fonds_region, {FONDS: FONDS_COLORS}),
        hide_index=True,
        use_container_width=True,
        column_config={
            **stats_col_config,
            "Médiane": st.column_config.ProgressColumn(
                format="%,d €", min_value=0, max_value=int(stats_fonds_region["Médiane"].max())
            ),
        },
    )

    st.markdown("**Visualisation (boîtes à moustaches)**")
    st.caption(
        "Chaque boîte représente la médiane et l'écart interquartile (IQR) du groupe ; les points "
        "au-delà des moustaches sont les opérations à montant atypique."
    )
    echelle_box_region = st.radio("Échelle ", ["Logarithmique", "Linéaire"], horizontal=True, key=f"echelle_box{key_suffix}")
    box_col_fonds_region, box_col_objectif_region = st.columns(2)
    with box_col_fonds_region:
        st.plotly_chart(
            build_boxplot(df_region_ops, FONDS, log_y=echelle_box_region == "Logarithmique"), use_container_width=True
        )
    with box_col_objectif_region:
        st.plotly_chart(
            build_boxplot(
                df_region_ops, LEVEL1, log_y=echelle_box_region == "Logarithmique", color_map=OBJECTIF_STRATEGIQUE_COLORS
            ),
            use_container_width=True,
        )

    st.markdown("**Opérations à montant atypique**")
    st.caption(
        "Opérations dont le montant s'écarte fortement de la distribution habituelle de son fonds "
        "(méthode IQR, calculée séparément par Fonds — FEDER, FSE+ et FTJ n'ont pas la même échelle "
        "de montants) — à examiner, sans présumer d'une anomalie : un montant élevé peut aussi "
        "correspondre à un projet structurant légitime."
    )
    outliers_region = detect_outliers(df_region_ops, group_col=FONDS)
    st.caption(f"{len(outliers_region)} opération(s) hors de l'intervalle interquartile habituel.")
    outliers_region_table = outliers_region[["Intitulé du projet", "Nom du bénéficiaire", FONDS, "Montant UE"]].head(50)
    st.dataframe(
        style_categorical_columns(outliers_region_table, {FONDS: FONDS_COLORS}),
        hide_index=True,
        use_container_width=True,
        column_config={
            "Montant UE": st.column_config.ProgressColumn(
                format="%,d €",
                min_value=0,
                max_value=int(outliers_region_table["Montant UE"].max()) if len(outliers_region_table) else 1,
            )
        },
    )

    st.markdown("**Concentration par bénéficiaire**")
    st.caption(
        f"Bénéficiaires cumulant le plus de montant UE, tous projets confondus dans {region_label} — vue "
        "d'ensemble des acteurs les plus représentés dans le portefeuille."
    )
    st.plotly_chart(build_pareto_beneficiaires(df_region_ops), use_container_width=True)
    with st.expander("Courbe de Lorenz (détail statistique de la concentration)"):
        st.caption(
            "Autre lecture de la même concentration : % cumulé de bénéficiaires (du plus petit au "
            "plus gros) vs % cumulé du montant — plus la courbe s'éloigne de la diagonale "
            "(égalité parfaite), plus le montant est concentré sur peu de bénéficiaires."
        )
        st.plotly_chart(build_lorenz_beneficiaires(df_region_ops), use_container_width=True)

    render_top_beneficiaires_drilldown(df_region_ops, montant_col_config, key=f"top_beneficiaires_region_{key_suffix}")

    st.markdown("**Opérations rapprochées par bénéficiaire**")
    st.caption(
        "On regarde ici de près les opérations d'un même bénéficiaire dont le montant et la date de "
        "démarrage sont proches."
    )
    proches_region, grands_regroupements_region, inter_fonds_region = detect_regroupements_beneficiaire(df_region_ops)

    st.caption(
        f"Petits regroupements (2 à 3 opérations) : {len(proches_region)} bénéficiaire(s). Les "
        "programmes découpés en lots (nombreuses opérations très proches par construction) peuvent "
        "malgré tout apparaître si le nombre de lots reste faible."
    )
    if len(proches_region):
        st.dataframe(
            proches_region.head(50),
            hide_index=True,
            use_container_width=True,
            column_config={"Montant UE cumulé": montant_col_config},
        )

    st.caption(
        f"Grands regroupements (4 opérations ou plus) : {len(grands_regroupements_region)} "
        "bénéficiaire(s). Le coefficient de variation indique la dispersion des montants au sein du "
        "regroupement (proche de 0 : montants quasi identiques ; élevé : montants très inégaux, ex. "
        "plusieurs lots de tailles différentes)."
    )
    if len(grands_regroupements_region):
        st.dataframe(
            grands_regroupements_region.head(50),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Montant UE cumulé": montant_col_config,
                "Coeff. de variation": st.column_config.NumberColumn(format="%.2f"),
            },
        )

    st.markdown("**Regroupements inter-fonds**")
    st.caption(
        f"{len(inter_fonds_region)} bénéficiaire(s) avec des opérations rapprochées (montant et date "
        "proches) couvrant plus d'un Fonds (ex. FEDER + FSE+) — signal plus fort qu'un regroupement "
        "intra-programme (lots d'un même accord-cadre, cas le plus fréquent ci-dessus), à recouper, "
        "pas une preuve en soi."
    )
    if len(inter_fonds_region):
        st.dataframe(
            inter_fonds_region,
            hide_index=True,
            use_container_width=True,
            column_config={"Montant UE cumulé": montant_col_config},
        )
    else:
        st.caption("Aucun cas détecté sur le périmètre actuel.")

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
        style_categorical_columns(cofinancement_fonds_region, {FONDS: FONDS_COLORS}),
        hide_index=True,
        use_container_width=True,
        column_config={
            "Taux moyen": st.column_config.ProgressColumn(
                format="percent", min_value=0, max_value=max(1.0, cofinancement_fonds_region["Taux moyen"].max())
            ),
            "Taux médian": taux_col_config,
        },
    )

    cofinancement_outliers_region = detect_cofinancement_outliers(df_region_ops).assign(
        **{"Montant hors UE": lambda d: d["Total des dépenses éligibles"] - d["Montant UE"]}
    )
    st.caption(f"{len(cofinancement_outliers_region)} opération(s) à taux de cofinancement atypique (méthode IQR).")
    cofinancement_outliers_region_table = cofinancement_outliers_region[
        [
            "Intitulé du projet",
            "Nom du bénéficiaire",
            FONDS,
            "Total des dépenses éligibles",
            "Montant UE",
            "Montant hors UE",
            "Taux de cofinancement",
        ]
    ].head(50)
    st.dataframe(
        style_categorical_columns(cofinancement_outliers_region_table, {FONDS: FONDS_COLORS}),
        hide_index=True,
        use_container_width=True,
        column_config={
            "Taux de cofinancement": taux_col_config,
            "Total des dépenses éligibles": montant_col_config,
            "Montant UE": st.column_config.ProgressColumn(
                format="%,d €",
                min_value=0,
                max_value=int(cofinancement_outliers_region_table["Montant UE"].max())
                if len(cofinancement_outliers_region_table)
                else 1,
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
    incoherentes_region = detect_incoherent_cofinancement(df_region_ops)
    st.caption(f"{len(incoherentes_region)} opération(s) où le montant UE dépasse le total des dépenses éligibles.")
    if len(incoherentes_region):
        incoherentes_region_table = incoherentes_region[
            ["Intitulé du projet", "Nom du bénéficiaire", FONDS, "Total des dépenses éligibles", "Montant UE", "Taux de cofinancement"]
        ].head(50)
        st.dataframe(
            style_categorical_columns(incoherentes_region_table, {FONDS: FONDS_COLORS}),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Total des dépenses éligibles": montant_col_config,
                "Montant UE": st.column_config.ProgressColumn(
                    format="%,d €", min_value=0, max_value=int(incoherentes_region_table["Montant UE"].max())
                ),
                "Taux de cofinancement": taux_col_config,
            },
        )
