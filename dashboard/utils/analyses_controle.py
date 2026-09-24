"""Sections de l'onglet « Analyses & contrôle », partagées entre Accueil (vue nationale),
Vue Régionale, Volet National (issue #160) et la page 2014-2020 (issue #157).

Chaque page compose ces sections dans le même ordre — introduction et distribution,
cofinancement, dispersion, montants atypiques, concentration par bénéficiaire,
regroupements, cohérence des montants — et n'écrit elle-même que ce qui lui est propre :
le plafond de sa catégorie de région (`region_analysis.render_region_audit`), les
analyses par région et par catégorie de la vue nationale (`Accueil.py`), ou les plafonds
et mentions propres à la période 2014-2020 (`pages/5_Période_2014-2020.py`).

`key_suffix` rend uniques les clés des widgets d'une page à l'autre ; les clés produites
sont celles d'avant l'extraction, pour ne pas réinitialiser les choix de l'utilisateur.
"""

import streamlit as st

from utils.stats import (
    build_boxplot,
    build_histogram,
    build_lorenz_beneficiaires,
    build_pareto_beneficiaires,
    compute_cofinancement_table,
    compute_stats_table,
    detect_cofinancement_outliers,
    detect_incoherent_cofinancement,
    detect_outliers,
    detect_regroupements_beneficiaire,
    render_top_beneficiaires_drilldown,
)
from utils.table_style import text_widths
from utils.themes import FONDS_COLORS, OBJECTIF_STRATEGIQUE_COLORS, style_categorical_columns

FONDS, LEVEL1 = "Fonds", "Objectif stratégique"

# Les seules colonnes que lit detect_regroupements_beneficiaire (et _cluster_operations_proches) :
# le cache ne hache qu'elles, et pas `regions_modernes` (des listes) ni le reste des
# opérations. Une colonne oubliée ici lève une KeyError que les tests de fumée attrapent.
COLONNES_REGROUPEMENT = [
    "Nom du bénéficiaire",
    "Numéro Opération",
    "Intitulé du projet",
    "Libellé Programme",
    FONDS,
    "Date de début de l'opération",
    "Montant UE",
]


def montant_col_config():
    return st.column_config.NumberColumn(format="%,d €")


def taux_col_config():
    return st.column_config.NumberColumn(format="percent")


def stats_col_config():
    """Colonnes de `compute_stats_table` : réutilisé par Accueil pour son tableau par région."""
    return {
        "Médiane": montant_col_config(),
        "Écart-type": montant_col_config(),
        "cv": st.column_config.NumberColumn(
            "Coeff. de variation", help="Écart-type / médiane — dispersion relative, comparable entre groupes de tailles différentes"
        ),
        "concentration_top10": st.column_config.NumberColumn(
            "Concentration (top 10%)", format="percent", help="Part du montant total portée par les 10% de projets les plus importants du groupe"
        ),
    }


def _montant_ue_progress(table, colonne="Montant UE"):
    return st.column_config.ProgressColumn(
        format="%,d €", min_value=0, max_value=int(table[colonne].max()) if len(table) else 1
    )


def render_introduction_distribution(df_ops, perimetre, key_suffix):
    """perimetre : complément de « Distribution des montants UE par opération, … »
    (« pour Bretagne », « à l'échelle nationale »)."""
    st.caption(
        "Ces indicateurs complètent les agrégats de base (somme, moyenne) affichés dans la vue "
        "d'ensemble : ils renseignent sur la dispersion des montants, la concentration du "
        "portefeuille et la cohérence des taux de cofinancement — des repères usuels pour l'analyse "
        "de dépense publique."
    )

    st.caption(
        f"Distribution des montants UE par opération, {perimetre}. Ces montants sont très "
        "asymétriques (majorité de petites opérations, quelques grands projets) : l'échelle "
        "logarithmique rend la forme de la distribution plus lisible."
    )
    echelle_hist = st.radio("Échelle", ["Logarithmique", "Linéaire"], horizontal=True, key=f"echelle_hist{key_suffix}")
    st.plotly_chart(
        build_histogram(df_ops, log_x=echelle_hist == "Logarithmique", color_col=FONDS, color_map=FONDS_COLORS),
        width='stretch',
    )


def render_taux_cofinancement(df_ops, caption, plafond=None):
    """Tableau des taux par fonds. Avec `plafond` (périmètre d'une seule catégorie de région),
    ajoute l'écart du taux moyen à ce plafond."""
    st.markdown("**Taux de cofinancement UE**")
    st.caption(caption)
    cofinancement_fonds = compute_cofinancement_table(df_ops, FONDS).rename(
        columns={"taux_moyen": "Taux moyen", "taux_median": "Taux médian", "count": "Nb projets"}
    )
    if plafond is not None:
        cofinancement_fonds["Écart au plafond"] = cofinancement_fonds["Taux moyen"] - plafond
    st.dataframe(
        style_categorical_columns(cofinancement_fonds, {FONDS: FONDS_COLORS}),
        hide_index=True,
        width='stretch',
        column_config={
            "Taux moyen": st.column_config.ProgressColumn(
                format="percent", min_value=0, max_value=max(1.0, plafond or 0, cofinancement_fonds["Taux moyen"].max())
            ),
            "Taux médian": taux_col_config(),
            "Écart au plafond": st.column_config.NumberColumn(
                format="percent", help="Taux moyen observé moins le plafond réglementaire — positif si le taux moyen dépasse le plafond"
            ),
        },
    )


def render_cofinancement_atypique(df_ops, colonnes_sup=()):
    """colonnes_sup : colonnes texte ajoutées après « Fonds » (« Région de l'opération » en
    vue nationale)."""
    cofinancement_outliers = detect_cofinancement_outliers(df_ops).assign(
        **{"Montant hors UE": lambda d: d["Total des dépenses éligibles"] - d["Montant UE"]}
    )
    st.caption(
        f"{len(cofinancement_outliers)} opération(s) à taux de cofinancement atypique par rapport aux "
        "autres opérations **du même fonds** (méthode IQR)."
    )
    cofinancement_outliers_table = cofinancement_outliers[
        [
            "Intitulé du projet",
            "Nom du bénéficiaire",
            FONDS,
            *colonnes_sup,
            "Total des dépenses éligibles",
            "Montant UE",
            "Montant hors UE",
            "Taux de cofinancement",
        ]
    ].head(50)
    st.dataframe(
        style_categorical_columns(cofinancement_outliers_table, {FONDS: FONDS_COLORS}),
        hide_index=True,
        width='stretch',
        column_config={
            **text_widths("Intitulé du projet", "Nom du bénéficiaire", *colonnes_sup),
            "Taux de cofinancement": taux_col_config(),
            "Total des dépenses éligibles": montant_col_config(),
            "Montant UE": _montant_ue_progress(cofinancement_outliers_table),
            "Montant hors UE": montant_col_config(),
        },
    )


def render_dispersion(df_ops, key_suffix, par_objectif=True):
    """Statistiques et boîte à moustaches par fonds côte à côte, puis par objectif stratégique.
    Retourne le choix d'échelle, que la vue nationale réutilise pour sa boîte par région.

    par_objectif=False retire la boîte par objectif stratégique : 2014-2020 n'a pas de
    dimension thématique (#82), et un bloc sans équivalent disparaît plutôt que de
    s'afficher vide (#83)."""
    st.caption(
        "La médiane et l'écart-type mesurent la dispersion des montants au sein d'un groupe. Le "
        "coefficient de variation (écart-type / médiane) rend cette dispersion comparable entre "
        "groupes de tailles très différentes. La concentration indique la part du montant total "
        "portée par les 10% de projets les plus importants du groupe. Chaque boîte à moustaches "
        "représente la médiane et l'écart interquartile (IQR) ; les points au-delà des moustaches "
        "sont les opérations à montant atypique."
    )
    echelle_box = st.radio(
        "Échelle des boîtes à moustaches", ["Logarithmique", "Linéaire"], horizontal=True, key=f"echelle_box{key_suffix}"
    )
    log_y = echelle_box == "Logarithmique"

    col_fonds, box_col_fonds = st.columns(2)
    with col_fonds:
        st.markdown("**Médiane, écart-type et concentration par fonds**")
        stats_fonds = compute_stats_table(df_ops, FONDS).rename(
            columns={"mediane": "Médiane", "ecart_type": "Écart-type", "count": "Nb projets"}
        )
        st.dataframe(
            style_categorical_columns(stats_fonds, {FONDS: FONDS_COLORS}),
            hide_index=True,
            width='stretch',
            column_config={
                **stats_col_config(),
                "Médiane": st.column_config.ProgressColumn(format="%,d €", min_value=0, max_value=int(stats_fonds["Médiane"].max())),
            },
        )
    with box_col_fonds:
        st.plotly_chart(build_boxplot(df_ops, FONDS, log_y=log_y, color_map=FONDS_COLORS), width='stretch')

    if not par_objectif:
        return echelle_box
    st.markdown("**Distribution par objectif stratégique**")
    st.plotly_chart(
        build_boxplot(df_ops, LEVEL1, log_y=log_y, color_map=OBJECTIF_STRATEGIQUE_COLORS),
        width='stretch',
    )
    return echelle_box


def render_montants_atypiques(df_ops, colonnes_sup=(), libelle_montant="Montant UE"):
    """colonnes_sup : comme `render_cofinancement_atypique`. libelle_montant : en-tête de la
    colonne montant (« Montant UE programmé » en 2014-2020, #83)."""
    st.markdown("**Opérations à montant atypique**")
    st.caption(
        "Opérations dont le montant s'écarte fortement de la distribution habituelle de son fonds "
        "(méthode IQR, calculée séparément par Fonds — les fonds n'ont pas la même échelle de "
        "montants) — à examiner, sans présumer d'une anomalie : un montant élevé peut aussi "
        "correspondre à un projet structurant légitime."
    )
    outliers = detect_outliers(df_ops, group_col=FONDS)
    st.caption(f"{len(outliers)} opération(s) hors de l'intervalle interquartile habituel.")
    outliers_table = (
        outliers[["Intitulé du projet", "Nom du bénéficiaire", FONDS, *colonnes_sup, "Montant UE"]]
        .head(50)
        .rename(columns={"Montant UE": libelle_montant})
    )
    st.dataframe(
        style_categorical_columns(outliers_table, {FONDS: FONDS_COLORS}),
        hide_index=True,
        width='stretch',
        column_config={
            **text_widths("Intitulé du projet", "Nom du bénéficiaire", *colonnes_sup),
            libelle_montant: _montant_ue_progress(outliers_table, libelle_montant),
        },
    )


def render_concentration_beneficiaires(df_ops, perimetre, key_top_beneficiaires):
    """perimetre : complément de « tous projets confondus » (« dans Bretagne », ou vide).
    key_top_beneficiaires : clé complète du sélecteur, les pages n'ayant pas suivi le même
    motif (voir inventaire de l'issue #160, écart E6)."""
    st.markdown("**Concentration par bénéficiaire**")
    st.caption(
        f"Bénéficiaires cumulant le plus de montant UE, tous projets confondus{perimetre} — vue "
        "d'ensemble des acteurs les plus représentés dans le portefeuille."
    )
    st.plotly_chart(build_pareto_beneficiaires(df_ops), width='stretch')
    with st.expander("Courbe de Lorenz (détail statistique de la concentration)"):
        st.caption(
            "Autre lecture de la même concentration : % cumulé de bénéficiaires (du plus petit au "
            "plus gros) vs % cumulé du montant — plus la courbe s'éloigne de la diagonale "
            "(égalité parfaite), plus le montant est concentré sur peu de bénéficiaires."
        )
        st.plotly_chart(build_lorenz_beneficiaires(df_ops), width='stretch')

    render_top_beneficiaires_drilldown(df_ops, montant_col_config(), key=key_top_beneficiaires)


@st.cache_data(max_entries=16, show_spinner="Recherche des opérations rapprochées…")
def _regroupements(df_regroupement):
    """En cache (#166) : 14 s sur les 54 755 opérations d'Ensemble national 2014-2020, à
    chaque rendu de l'onglet sinon. `max_entries` borne la mémoire (Streamlit Cloud, #130) :
    une entrée par périmètre et par filtre Fonds."""
    return detect_regroupements_beneficiaire(df_regroupement)


def render_regroupements(df_ops):
    """Opérations rapprochées par bénéficiaire (petits et grands regroupements), puis
    regroupements inter-fonds."""
    st.markdown("**Opérations rapprochées par bénéficiaire**")
    st.caption(
        "On regarde ici de près les opérations d'un même bénéficiaire dont le montant et la date de "
        "démarrage sont proches."
    )
    proches, grands_regroupements, inter_fonds = _regroupements(df_ops[COLONNES_REGROUPEMENT])

    st.caption(
        f"Petits regroupements (2 à 3 opérations) : {len(proches)} bénéficiaire(s). Les "
        "programmes découpés en lots (nombreuses opérations très proches par construction) peuvent "
        "malgré tout apparaître si le nombre de lots reste faible."
    )
    if len(proches):
        st.dataframe(
            proches.head(50),
            hide_index=True,
            width='stretch',
            column_config={**text_widths("Nom du bénéficiaire", "Opérations", "Programme(s)"), "Montant UE cumulé": montant_col_config()},
        )

    st.caption(
        f"Grands regroupements (4 opérations ou plus) : {len(grands_regroupements)} "
        "bénéficiaire(s). Le coefficient de variation indique la dispersion des montants au sein du "
        "regroupement (proche de 0 : montants quasi identiques ; élevé : montants très inégaux, ex. "
        "plusieurs lots de tailles différentes)."
    )
    if len(grands_regroupements):
        st.dataframe(
            grands_regroupements.head(50),
            hide_index=True,
            width='stretch',
            column_config={
                **text_widths("Nom du bénéficiaire"),
                "Montant UE cumulé": montant_col_config(),
                "Coeff. de variation": st.column_config.NumberColumn(format="%.2f"),
            },
        )

    st.markdown("**Regroupements inter-fonds**")
    st.caption(
        f"{len(inter_fonds)} bénéficiaire(s) avec des opérations rapprochées (montant et date "
        "proches) couvrant plus d'un Fonds (ex. FEDER + FSE+) — signal plus fort qu'un regroupement "
        "intra-programme (lots d'un même accord-cadre, cas le plus fréquent ci-dessus), à recouper, "
        "pas une preuve en soi."
    )
    if len(inter_fonds):
        st.dataframe(
            inter_fonds,
            hide_index=True,
            width='stretch',
            column_config={**text_widths("Nom du bénéficiaire", "Programme(s)", "Opérations"), "Montant UE cumulé": montant_col_config()},
        )
    else:
        st.caption("Aucun cas détecté sur le périmètre actuel.")


def render_coherence_montants(df_ops, precision=""):
    """precision : phrase ajoutée à la légende, pour ce qui est propre à une période."""
    st.markdown("**Cohérence des montants**")
    st.caption(
        "Contrôle de cohérence (pas une question de distribution) : opérations où le montant UE "
        "dépasse le total des dépenses éligibles, ce qui correspondrait à un taux de cofinancement "
        "supérieur à 100%, normalement impossible — à vérifier, potentiel signal de qualité de données."
        + precision
    )
    incoherentes = detect_incoherent_cofinancement(df_ops)
    st.caption(f"{len(incoherentes)} opération(s) où le montant UE dépasse le total des dépenses éligibles.")
    if len(incoherentes):
        incoherentes_table = incoherentes[
            ["Intitulé du projet", "Nom du bénéficiaire", FONDS, "Total des dépenses éligibles", "Montant UE", "Taux de cofinancement"]
        ].head(50)
        st.dataframe(
            style_categorical_columns(incoherentes_table, {FONDS: FONDS_COLORS}),
            hide_index=True,
            width='stretch',
            column_config={
                **text_widths("Intitulé du projet", "Nom du bénéficiaire"),
                "Total des dépenses éligibles": montant_col_config(),
                "Montant UE": st.column_config.ProgressColumn(
                    format="%,d €", min_value=0, max_value=int(incoherentes_table["Montant UE"].max())
                ),
                "Taux de cofinancement": taux_col_config(),
            },
        )
