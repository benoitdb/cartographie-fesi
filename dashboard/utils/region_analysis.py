import plotly.express as px
import streamlit as st

from utils.analyses_controle import (
    montant_col_config,
    render_cofinancement_atypique,
    render_coherence_montants,
    render_concentration_beneficiaires,
    render_dispersion,
    render_introduction_distribution,
    render_montants_atypiques,
    render_regroupements,
    render_taux_cofinancement,
    taux_col_config,
)
from utils.cofinancement import plafond_categorie
from utils.plot_style import style_hover
from utils.retour_experience import RETOUR_EXPERIENCE_ANCT, SOURCE_ANCT
from utils.stats import (
    build_cofinancement_categorie_chart,
    build_cumulative_curve,
    build_fonds_barchart,
    build_portfolio_scatter_comparison,
    detect_cofinancement_superieur_plafond,
)
from utils.table_style import text_widths
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
            region_ops.groupby("Fonds")
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
        st.plotly_chart(fig_region_fonds, width='stretch')
    with progress_col:
        mode_courbe = st.radio("Courbe cumulée", ["Montant", "%"], horizontal=True, key=f"mode_courbe{key_suffix}")
        mode_courbe_val = "pourcentage" if mode_courbe == "%" else "montant"
        st.plotly_chart(
            build_cumulative_curve(region_ops, color_map=FONDS_COLORS, totaux_ref=programme_totals, mode=mode_courbe_val),
            width='stretch',
        )
        st.caption(
            "Engagement UE cumulé dans le temps. Basé sur la date de début de l'opération — environ 60% "
            "des dates sont arrondies au 1ᵉʳ janvier (date administrative plutôt qu'une date de démarrage "
            "précise), d'où des paliers plutôt qu'une progression lissée. Cliquer sur un fonds dans la "
            "légende pour l'isoler ou le masquer. En mode %, seuls les fonds avec une enveloppe programmée "
            "connue sont affichés."
        )

    df_region_ops = region_ops.copy()
    df_region_ops[LEVEL1] = df_region_ops[LEVEL1].fillna("Non spécifié")
    df_region_ops[LEVEL2] = df_region_ops[LEVEL2].fillna("Non spécifié")
    df_region_ops[LEVEL3] = df_region_ops[LEVEL3].fillna("Non spécifié")

    # Vue d'ensemble : fonds > objectif stratégique > objectif spécifique
    st.subheader("Fonds, objectifs stratégiques et spécifiques")

    fig_hierarchy = build_hierarchy_treemap(df_region_ops, [FONDS, LEVEL1, LEVEL2])

    st.plotly_chart(fig_hierarchy, width='stretch')

    # Détail par fonds : objectif stratégique > spécifique > type d'intervention
    st.subheader("Détail par fonds")

    fonds_presents = sorted(df_region_ops[FONDS].unique())
    fonds_cols = st.columns(len(fonds_presents))

    for col, fonds in zip(fonds_cols, fonds_presents, strict=True):
        with col:
            st.markdown(f"**{fonds}**")
            df_fonds = df_region_ops[df_region_ops[FONDS] == fonds]
            fig_fonds_detail = build_hierarchy_treemap(
                df_fonds, [LEVEL1, LEVEL2, LEVEL3], color_map=OBJECTIF_STRATEGIQUE_COLORS
            )
            st.plotly_chart(fig_fonds_detail, width='stretch')

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
        width='stretch',
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
    st.plotly_chart(style_hover(fig_region_os), width='stretch')

    os_presents = set(df_region_os[LEVEL1])
    os_avec_retour = [os for os in os_presents if os in RETOUR_EXPERIENCE_ANCT]
    if os_avec_retour:
        with st.expander("Retour d'expérience FEDER 2014-2020 (ANCT)"):
            for os in sorted(os_avec_retour):
                retour = RETOUR_EXPERIENCE_ANCT[os]
                st.markdown(f"**{os}** — {retour['label_court']} *(source 14-20 : {retour['ot_source']})*")
                cols = st.columns(2)
                with cols[0]:
                    st.markdown("Écueils identifiés :")
                    for e in retour["ecueils"]:
                        st.markdown(f"- **{e['theme']}** — {e['texte']}")
                with cols[1]:
                    st.markdown("Facteurs favorisants :")
                    for f in retour["facteurs_favorisants"]:
                        st.markdown(f"- {f}")
            st.caption(SOURCE_ANCT)


def render_region_audit(df_region_ops, region_label, key_suffix="", region_meta=None):
    """Espace Autorité d'audit : dispersion/concentration des montants, opérations atypiques,
    regroupements par bénéficiaire (dont inter-fonds, #23), cofinancement atypique, cohérence
    des montants — indicateurs usuels de contrôle de dépense publique, pas de description
    structurelle (voir render_region_ensemble pour ça). Les sections sont partagées avec la
    vue nationale (`utils/analyses_controle.py`, issue #160) ; seul le plafond de la catégorie
    de région est propre à cette vue.

    region_meta (optionnel, dict avec "categorie_ue"/"ultraperipherique") : permet de comparer
    le taux de cofinancement observé au plafond réglementaire de la catégorie de région
    (utils/cofinancement.plafond_categorie) — absent pour le Volet national, qui ne relève
    d'aucune catégorie de région unique."""
    plafond = plafond_categorie(region_meta.get("categorie_ue"), region_meta.get("ultraperipherique")) if region_meta else None

    render_introduction_distribution(df_region_ops, f"pour {region_label}", key_suffix)

    if plafond is not None:
        categorie_affichee = region_meta.get("categorie_ue") or "Non classifiée"
        mention_rup = " + allocation RUP (art. 349 TFUE)" if region_meta.get("ultraperipherique") else ""
        caption_taux = (
            f"Plafond réglementaire de cofinancement UE pour {region_label} ({categorie_affichee}{mention_rup}) : "
            f"**{plafond:.0%}** (règlement (UE) 2021/1060, art. 112). Un taux observé au-delà de ce plafond est "
            "un signal réglementaire, pas seulement statistique — voir la sous-section dédiée plus bas."
        )
    else:
        caption_taux = (
            "Le taux de cofinancement est plafonné réglementairement selon la catégorie de région "
            "(plafond non déterminable ici, catégorie non renseignée) ; un taux atypique peut signaler une "
            "opération à vérifier."
        )
    render_taux_cofinancement(df_region_ops, caption_taux, plafond=plafond)
    if plafond is not None:
        _render_depassements_plafond(df_region_ops, plafond)
    render_cofinancement_atypique(df_region_ops)

    render_dispersion(df_region_ops, key_suffix)
    render_montants_atypiques(df_region_ops)
    render_concentration_beneficiaires(df_region_ops, f" dans {region_label}", f"top_beneficiaires_region_{key_suffix}")
    render_regroupements(df_region_ops)
    render_coherence_montants(df_region_ops)


def _render_depassements_plafond(df_region_ops, plafond):
    """Taux par fonds face au plafond de la catégorie, puis opérations qui le dépassent."""
    df_cofinancement_region_chart = (
        df_region_ops.groupby(FONDS)
        .agg(montant_ue=("Montant UE", "sum"), total_depenses=("Total des dépenses éligibles", "sum"))
        .reset_index()
        .rename(columns={FONDS: "Fonds"})
    )
    df_cofinancement_region_chart["plafond"] = plafond
    st.plotly_chart(
        build_cofinancement_categorie_chart(df_cofinancement_region_chart, label_col="Fonds", height=250),
        width='stretch',
    )

    depassements_plafond = detect_cofinancement_superieur_plafond(df_region_ops, plafond).assign(
        **{"Montant hors UE": lambda d: d["Total des dépenses éligibles"] - d["Montant UE"]}
    )
    st.caption(
        f"{len(depassements_plafond)} opération(s) dont le taux de cofinancement UE dépasse le plafond "
        f"réglementaire de {plafond:.0%} — signal réglementaire (pas statistique), potentiel dépassement à "
        "vérifier plutôt qu'une preuve en soi (marge d'erreur possible sur la catégorie de région retenue, "
        "voir la note méthodologique de la Vue Régionale)."
    )
    if len(depassements_plafond):
        depassements_plafond_table = depassements_plafond[
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
            style_categorical_columns(depassements_plafond_table, {FONDS: FONDS_COLORS}),
            hide_index=True,
            width='stretch',
            column_config={
                **text_widths("Intitulé du projet", "Nom du bénéficiaire"),
                "Taux de cofinancement": taux_col_config(),
                "Total des dépenses éligibles": montant_col_config(),
                "Montant UE": st.column_config.ProgressColumn(
                    format="%,d €",
                    min_value=0,
                    max_value=int(depassements_plafond_table["Montant UE"].max()),
                ),
                "Montant hors UE": montant_col_config(),
            },
        )
