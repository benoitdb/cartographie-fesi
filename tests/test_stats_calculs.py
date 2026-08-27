"""Couche de calcul de `utils/stats.py` : c'est là que naissent les chiffres faux.

Les tests de fumée (`test_dashboard_pages.py`) prouvent qu'une page se rend ;
ils ne disent rien de la justesse de ce qu'elle affiche. Ici on ne rend rien :
on éprouve les fonctions de calcul et de détection sur des cas construits, dont
les valeurs attendues se posent à la main.

Priorité donnée aux invariants documentés dans le code et aux régressions déjà
constatées une fois (bornes IQR par fonds, montant manquant devenu `NaN` par
`to_dict("records")`, dépassement d'enveloppe à ne pas masquer) : ce sont les
seules pour lesquelles on sait que l'erreur est possible, parce qu'elle a eu
lieu.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "dashboard"))

from utils.stats import (  # noqa: E402
    build_cumulative_curve,
    build_fonds_barchart,
    compute_cofinancement_table,
    compute_stats_table,
    compute_top_beneficiaires,
    detect_beneficiaires_multi_region,
    detect_cofinancement_outliers,
    detect_cofinancement_superieur_plafond,
    detect_incoherent_cofinancement,
    detect_outliers,
    detect_regroupements_beneficiaire,
)

COLONNES_REGROUPEMENT = [
    "Nom du bénéficiaire",
    "Numéro Opération",
    "Intitulé du projet",
    "Libellé Programme",
    "Fonds",
    "Date de début de l'opération",
    "Montant UE",
]


def operation(
    numero,
    beneficiaire="Bénéficiaire A",
    montant=100_000.0,
    date="2022-01-01",
    fonds="FEDER",
    programme="PO FEDER-FSE+ Occitanie",
):
    """Une ligne d'opération au format attendu par les fonctions de détection."""
    return {
        "Nom du bénéficiaire": beneficiaire,
        "Numéro Opération": numero,
        "Intitulé du projet": f"Projet {numero}",
        "Libellé Programme": programme,
        "Fonds": fonds,
        "Date de début de l'opération": date,
        "Montant UE": montant,
    }


# --- Statistiques descriptives -------------------------------------------------


def test_la_table_de_stats_donne_mediane_ecart_type_et_coefficient_de_variation():
    df = pd.DataFrame(
        {
            "Fonds": ["FEDER"] * 4 + ["FSE+"] * 4,
            "Montant UE": [100.0, 200.0, 300.0, 400.0, 10.0, 20.0, 30.0, 40.0],
        }
    )
    table = compute_stats_table(df, "Fonds").set_index("Fonds")

    assert table.loc["FEDER", "mediane"] == 250.0
    assert table.loc["FSE+", "mediane"] == 25.0
    assert table.loc["FEDER", "count"] == 4
    # Écart-type d'échantillon (ddof=1) : le même jeu ×10 donne un écart-type ×10,
    # donc un coefficient de variation identique — c'est tout l'intérêt du CV,
    # rendre comparables deux fonds d'échelles différentes.
    assert table.loc["FEDER", "ecart_type"] == pytest.approx(10 * table.loc["FSE+", "ecart_type"])
    assert table.loc["FEDER", "cv"] == pytest.approx(table.loc["FSE+", "cv"])


def test_la_table_de_stats_est_triee_par_mediane_decroissante():
    df = pd.DataFrame({"Fonds": ["FSE+", "FEDER"], "Montant UE": [10.0, 100.0]})
    assert compute_stats_table(df, "Fonds")["Fonds"].tolist() == ["FEDER", "FSE+"]


def test_un_groupe_a_operation_unique_ne_produit_ni_nan_ni_infini():
    """L'écart-type d'une seule valeur est `NaN` et une médiane nulle divise par
    zéro : les deux arrivent en vrai (un fonds à une seule opération dans une
    petite région) et remonteraient tels quels dans le tableau affiché."""
    df = pd.DataFrame({"Fonds": ["FTJ", "FEDER"], "Montant UE": [50_000.0, 0.0]})
    table = compute_stats_table(df, "Fonds").set_index("Fonds")

    assert table.loc["FTJ", "ecart_type"] == 0
    assert table.loc["FTJ", "cv"] == 0
    assert table.loc["FEDER", "cv"] == 0


def test_la_concentration_mesure_la_part_des_10_pourcent_de_plus_gros_projets():
    # 10 projets : les 10% les plus gros = 1 projet, qui porte 1000 sur 1090.
    df = pd.DataFrame({"Fonds": ["FEDER"] * 10, "Montant UE": [1000.0] + [10.0] * 9})
    concentration = compute_stats_table(df, "Fonds")["concentration_top10"].iloc[0]
    assert concentration == pytest.approx(1000 / 1090)


def test_la_concentration_d_un_groupe_a_montant_total_nul_vaut_zero():
    df = pd.DataFrame({"Fonds": ["FEDER"] * 3, "Montant UE": [0.0, 0.0, 0.0]})
    assert compute_stats_table(df, "Fonds")["concentration_top10"].iloc[0] == 0.0


# --- Valeurs atypiques ---------------------------------------------------------


def _portefeuille_deux_echelles():
    """30 opérations FSE+ autour de 100 k€ et 8 opérations FEDER autour de
    235 k€ — toutes régulièrement réparties, donc aucune n'est atypique au sein
    de son propre fonds. Reproduit la configuration réelle qui avait fait
    signaler à tort 502 opérations FEDER."""
    fse = [{"Fonds": "FSE+", "Montant UE": 90_000.0 + 1_000 * i} for i in range(30)]
    feder = [{"Fonds": "FEDER", "Montant UE": 200_000.0 + 10_000 * i} for i in range(8)]
    return pd.DataFrame(fse + feder)


def test_sans_groupe_les_bornes_communes_signalent_des_operations_normales():
    """Constat de référence du test suivant : avec une borne unique, la
    distribution du fonds majoritaire fixe le seuil et le fonds à plus grande
    échelle bascule en bloc du mauvais côté."""
    df = _portefeuille_deux_echelles()
    atypiques = detect_outliers(df)
    assert set(atypiques["Fonds"]) == {"FEDER"}
    assert len(atypiques) == 8


def test_les_bornes_calculees_par_fonds_ne_signalent_plus_ces_operations():
    df = _portefeuille_deux_echelles()
    assert detect_outliers(df, group_col="Fonds").empty


def test_une_operation_hors_norme_dans_son_propre_fonds_reste_signalee():
    """Le groupement par fonds ne doit pas neutraliser la détection : c'est le
    risque symétrique du test précédent."""
    df = pd.concat(
        [_portefeuille_deux_echelles(), pd.DataFrame([{"Fonds": "FEDER", "Montant UE": 5_000_000.0}])],
        ignore_index=True,
    )
    atypiques = detect_outliers(df, group_col="Fonds")
    assert atypiques["Montant UE"].tolist() == [5_000_000.0]


def test_les_valeurs_atypiques_sont_triees_du_plus_gros_montant_au_plus_petit():
    df = pd.DataFrame(
        {"Fonds": ["FEDER"] * 12, "Montant UE": [*[100.0 + i for i in range(10)], 9_000.0, 5_000.0]}
    )
    assert detect_outliers(df)["Montant UE"].tolist() == [9_000.0, 5_000.0]


# --- Cofinancement -------------------------------------------------------------


def test_la_table_de_cofinancement_donne_taux_moyen_et_median_par_groupe():
    df = pd.DataFrame(
        {
            "Fonds": ["FEDER", "FEDER", "FEDER", "FSE+"],
            "Taux de cofinancement": [0.4, 0.5, 0.9, 0.6],
        }
    )
    table = compute_cofinancement_table(df, "Fonds").set_index("Fonds")

    assert table.loc["FEDER", "taux_moyen"] == pytest.approx(0.6)
    assert table.loc["FEDER", "taux_median"] == 0.5
    assert table.loc["FEDER", "count"] == 3
    assert table.loc["FSE+", "taux_moyen"] == pytest.approx(0.6)


def test_la_table_de_cofinancement_est_triee_par_taux_moyen_decroissant():
    df = pd.DataFrame(
        {"Fonds": ["FSE+", "FEDER"], "Taux de cofinancement": [0.4, 0.8]},
    )
    assert compute_cofinancement_table(df, "Fonds")["Fonds"].tolist() == ["FEDER", "FSE+"]


def test_le_depassement_de_plafond_reglementaire_ne_depend_pas_de_la_distribution():
    """À ne pas confondre avec la détection statistique : ici la référence est
    le taux maximal légal, donc une opération à 90% est signalée même si toutes
    les autres sont au même niveau."""
    df = pd.DataFrame({"Taux de cofinancement": [0.9, 0.88, 0.5], "id": ["a", "b", "c"]})
    depassements = detect_cofinancement_superieur_plafond(df, plafond=0.85)
    assert depassements["id"].tolist() == ["a", "b"]


def test_un_taux_exactement_au_plafond_n_est_pas_un_depassement():
    df = pd.DataFrame({"Taux de cofinancement": [0.85]})
    assert detect_cofinancement_superieur_plafond(df, plafond=0.85).empty


def test_les_taux_statistiquement_atypiques_sont_detectes_par_l_ecart_a_l_iqr():
    df = pd.DataFrame({"Taux de cofinancement": [*[0.5 + 0.001 * i for i in range(10)], 0.95]})
    assert detect_cofinancement_outliers(df)["Taux de cofinancement"].tolist() == [0.95]


def test_un_montant_ue_superieur_aux_depenses_eligibles_est_incoherent():
    """Contrôle de cohérence, pas de distribution : un taux > 100% est
    impossible, quelle que soit la catégorie de région."""
    df = pd.DataFrame(
        {
            "Montant UE": [120.0, 80.0, 100.0],
            "Total des dépenses éligibles": [100.0, 100.0, 100.0],
        }
    )
    incoherentes = detect_incoherent_cofinancement(df)
    assert incoherentes["Montant UE"].tolist() == [120.0]


# --- Bénéficiaires -------------------------------------------------------------


def test_le_top_beneficiaires_cumule_les_montants_et_compte_les_projets():
    df = pd.DataFrame(
        {
            "Nom du bénéficiaire": ["Région X", "Région X", "Commune Y"],
            "Montant UE": [100.0, 200.0, 250.0],
        }
    )
    top = compute_top_beneficiaires(df).set_index("Nom du bénéficiaire")

    assert top.loc["Région X", "montant_ue_total"] == 300.0
    assert top.loc["Région X", "count"] == 2
    assert compute_top_beneficiaires(df)["Nom du bénéficiaire"].tolist() == ["Région X", "Commune Y"]


def test_le_top_beneficiaires_est_tronque_a_top_n():
    df = pd.DataFrame(
        {"Nom du bénéficiaire": [f"B{i}" for i in range(10)], "Montant UE": [float(i) for i in range(10)]}
    )
    assert len(compute_top_beneficiaires(df, top_n=3)) == 3


def test_deux_operations_proches_en_montant_et_en_date_forment_un_regroupement():
    df = pd.DataFrame(
        [
            operation("A1", montant=100_000.0, date="2022-01-01"),
            operation("A2", montant=105_000.0, date="2022-02-15"),
        ],
        columns=COLONNES_REGROUPEMENT,
    )
    petits, grands, inter_fonds = detect_regroupements_beneficiaire(df)

    assert len(petits) == 1
    assert petits["Nb opérations rapprochées"].iloc[0] == 2
    assert petits["Montant UE cumulé"].iloc[0] == 205_000.0
    assert grands.empty
    assert inter_fonds.empty


def test_des_operations_eloignees_en_date_ou_en_montant_ne_sont_pas_rapprochees():
    df = pd.DataFrame(
        [
            operation("A1", montant=100_000.0, date="2022-01-01"),
            # Même montant, mais 6 mois plus tard (> max_days).
            operation("A2", montant=100_000.0, date="2022-07-01"),
            # Même date que A1, mais montant 3× supérieur (> max_relative_diff).
            operation("A3", montant=300_000.0, date="2022-01-01"),
        ],
        columns=COLONNES_REGROUPEMENT,
    )
    petits, grands, _ = detect_regroupements_beneficiaire(df)
    assert petits.empty and grands.empty


def test_un_montant_manquant_ne_fait_pas_echouer_le_rapprochement():
    """`to_dict("records")` transforme une valeur manquante en `NaN`, qui est
    *vrai* en Python : une garde par simple test de vérité laissait passer le
    montant manquant jusqu'au calcul d'écart relatif (issue #27). Le voisin
    valide ne doit pas non plus être rapproché du `NaN`."""
    df = pd.DataFrame(
        [
            operation("A1", montant=float("nan"), date="2022-01-01"),
            operation("A2", montant=100_000.0, date="2022-01-05"),
        ],
        columns=COLONNES_REGROUPEMENT,
    )
    petits, grands, inter_fonds = detect_regroupements_beneficiaire(df)
    assert petits.empty and grands.empty and inter_fonds.empty


def test_au_dela_de_max_group_size_le_regroupement_bascule_dans_la_grande_table():
    df = pd.DataFrame(
        [operation(f"A{i}", montant=100_000.0, date=f"2022-01-0{i + 1}") for i in range(4)],
        columns=COLONNES_REGROUPEMENT,
    )
    petits, grands, _ = detect_regroupements_beneficiaire(df, max_group_size=3)

    assert petits.empty
    assert grands["Nb opérations rapprochées"].tolist() == [4]
    # Montants identiques : dispersion nulle, signature de lots de même taille.
    assert grands["Coeff. de variation"].iloc[0] == pytest.approx(0.0)


def test_un_regroupement_couvrant_plusieurs_fonds_a_sa_propre_table():
    df = pd.DataFrame(
        [
            operation("A1", montant=100_000.0, date="2022-01-01", fonds="FEDER"),
            operation("A2", montant=100_000.0, date="2022-01-10", fonds="FSE+"),
        ],
        columns=COLONNES_REGROUPEMENT,
    )
    petits, _, inter_fonds = detect_regroupements_beneficiaire(df)

    assert len(petits) == 1, "un regroupement inter-fonds reste aussi dans sa table de taille"
    assert inter_fonds["Fonds"].tolist() == ["FEDER; FSE+"]


def test_les_operations_de_beneficiaires_differents_ne_sont_jamais_rapprochees():
    df = pd.DataFrame(
        [
            operation("A1", beneficiaire="Commune de X", montant=100_000.0, date="2022-01-01"),
            operation("B1", beneficiaire="Commune de Y", montant=100_000.0, date="2022-01-02"),
        ],
        columns=COLONNES_REGROUPEMENT,
    )
    petits, grands, inter_fonds = detect_regroupements_beneficiaire(df)
    assert petits.empty and grands.empty and inter_fonds.empty


def test_sans_regroupement_les_trois_tables_gardent_leurs_colonnes():
    """Elles sont affichées telles quelles : un DataFrame vide sans colonnes
    ferait échouer la mise en forme au lieu de montrer une table vide."""
    df = pd.DataFrame([operation("A1")], columns=COLONNES_REGROUPEMENT)
    petits, grands, inter_fonds = detect_regroupements_beneficiaire(df)

    assert list(petits.columns)[:3] == ["Nom du bénéficiaire", "Nb opérations rapprochées", "Montant UE cumulé"]
    assert "Coeff. de variation" in grands.columns
    assert "Fonds" in inter_fonds.columns


def test_un_beneficiaire_present_dans_deux_regions_est_repere():
    df = pd.DataFrame(
        {
            "Nom du bénéficiaire": ["Société A", "Société A", "Société B"],
            "regions_modernes": [["Occitanie"], ["Bretagne"], ["Bretagne"]],
            "Fonds": ["FEDER", "FSE+", "FEDER"],
            "Numéro Opération": ["1", "2", "3"],
            "Montant UE": [100.0, 200.0, 999.0],
        }
    )
    multi = detect_beneficiaires_multi_region(df, fuzzy_clusters={})

    assert multi["Nom du bénéficiaire"].tolist() == ["Société A"]
    assert multi["Rapprochement"].iloc[0] == "exact"
    assert multi["Régions"].iloc[0] == "Bretagne, Occitanie"
    assert multi["Montant UE cumulé"].iloc[0] == 300.0


def test_deux_variantes_de_saisie_rapprochees_comptent_pour_un_seul_beneficiaire():
    df = pd.DataFrame(
        {
            "Nom du bénéficiaire": ["SA MARTIN", "S.A. MARTIN"],
            "regions_modernes": [["Occitanie"], ["Bretagne"]],
            "Fonds": ["FEDER", "FEDER"],
            "Numéro Opération": ["1", "2"],
            "Montant UE": [100.0, 200.0],
        }
    )
    clusters = {"SA MARTIN": "cluster-martin", "S.A. MARTIN": "cluster-martin"}
    multi = detect_beneficiaires_multi_region(df, fuzzy_clusters=clusters)

    assert len(multi) == 1
    assert multi["Rapprochement"].iloc[0] == "approché (variantes de saisie)"
    assert multi["Nom du bénéficiaire"].iloc[0] == "S.A. MARTIN / SA MARTIN"


def test_une_operation_sans_region_rattachee_ne_cree_pas_de_multi_region():
    """`regions_modernes` peut être `None` (opération non rattachée) : l'absence
    de région n'est pas une région de plus."""
    df = pd.DataFrame(
        {
            "Nom du bénéficiaire": ["Société A", "Société A"],
            "regions_modernes": [["Occitanie"], None],
            "Fonds": ["FEDER", "FEDER"],
            "Numéro Opération": ["1", "2"],
            "Montant UE": [100.0, 200.0],
        }
    )
    assert detect_beneficiaires_multi_region(df, fuzzy_clusters={}).empty


# --- Graphiques dont la logique porte un calcul --------------------------------


def test_le_barchart_par_fonds_empile_le_reste_a_engager():
    df_fonds = pd.DataFrame(
        {"fonds": ["FEDER", "FSE+"], "montant_ue_total": [800.0, 150.0], "count": [10, 5]}
    )
    fig = build_fonds_barchart(df_fonds, color_map={}, totaux_programme={"FEDER": 1000.0, "FSE+": 100.0})

    engage, reste = fig.data[0], fig.data[1]
    assert list(engage.y) == [800.0, 150.0]
    # FSE+ dépasse son enveloppe : son reste est plancher à 0, jamais négatif —
    # une barre négative empilée descendrait sous l'axe.
    assert list(reste.y) == [200.0, 0.0]


def test_le_barchart_par_fonds_n_empile_rien_sans_montants_programmes():
    df_fonds = pd.DataFrame({"fonds": ["FEDER"], "montant_ue_total": [800.0], "count": [10]})
    assert len(build_fonds_barchart(df_fonds, color_map={}).data) == 1


def test_un_fonds_absent_du_tableau_des_programmations_n_a_pas_de_reste():
    """Tous les fonds ne sont pas au Tableau 9B : l'absence ne doit pas faire
    échouer le graphe ni inventer un reste."""
    df_fonds = pd.DataFrame(
        {"fonds": ["FEDER", "FTJ"], "montant_ue_total": [800.0, 50.0], "count": [10, 2]}
    )
    fig = build_fonds_barchart(df_fonds, color_map={}, totaux_programme={"FEDER": 1000.0})
    assert list(fig.data[1].y) == [200.0, 0.0]


def test_la_courbe_cumulee_cumule_par_categorie_et_dans_l_ordre_des_dates():
    df = pd.DataFrame(
        {
            "Date de début de l'opération": ["2022-03-01", "2022-01-01", "2022-01-01"],
            "Montant UE": [50.0, 100.0, 25.0],
            "Fonds": ["FEDER", "FEDER", "FSE+"],
        }
    )
    fig = build_cumulative_curve(df)
    courbes = {trace.name: list(trace.y) for trace in fig.data}

    assert courbes["FEDER"] == [100.0, 150.0]
    assert courbes["FSE+"] == [25.0]


def test_en_mode_pourcentage_la_courbe_rapporte_le_cumule_a_l_enveloppe():
    df = pd.DataFrame(
        {
            "Date de début de l'opération": ["2022-01-01", "2022-03-01"],
            "Montant UE": [200.0, 300.0],
            "Fonds": ["FEDER", "FEDER"],
        }
    )
    fig = build_cumulative_curve(df, totaux_ref={"FEDER": 1000.0}, mode="pourcentage")
    assert list(fig.data[0].y) == [0.2, 0.5]


def test_en_mode_pourcentage_une_categorie_sans_enveloppe_est_exclue():
    """Il n'y a rien à quoi rapporter son cumul : la tracer donnerait un
    pourcentage d'un montant inconnu."""
    df = pd.DataFrame(
        {
            "Date de début de l'opération": ["2022-01-01", "2022-01-01"],
            "Montant UE": [200.0, 100.0],
            "Fonds": ["FEDER", "FTJ"],
        }
    )
    fig = build_cumulative_curve(df, totaux_ref={"FEDER": 1000.0}, mode="pourcentage")
    assert [trace.name for trace in fig.data] == ["FEDER"]


def test_le_mode_pourcentage_retombe_sur_les_montants_si_aucune_categorie_presente_n_a_d_enveloppe():
    """totaux_ref non vide mais qui ne couvre aucun fonds présent (ex. sélection limitée à
    FEAD ou FEDER-FSE en 2014-2020, deux fonds sans enveloppe programmée, #100) : sans repli,
    le filtre `isin(totaux_ref)` laisse un DataFrame vide et le repère annuel qui suit
    (range sur un min/max NaN) lève un TypeError plutôt que d'afficher la courbe en montant."""
    df = pd.DataFrame(
        {
            "Date de début de l'opération": ["2022-01-01", "2022-03-01"],
            "Montant UE": [200.0, 300.0],
            "Fonds": ["FTJ", "FTJ"],
        }
    )
    fig = build_cumulative_curve(df, totaux_ref={"FEDER": 1000.0}, mode="pourcentage")
    assert list(fig.data[0].y) == [200.0, 500.0]


def test_le_mode_pourcentage_retombe_sur_les_montants_sans_enveloppe_connue():
    df = pd.DataFrame(
        {
            "Date de début de l'opération": ["2022-01-01", "2022-03-01"],
            "Montant UE": [200.0, 300.0],
            "Fonds": ["FEDER", "FEDER"],
        }
    )
    fig = build_cumulative_curve(df, totaux_ref={}, mode="pourcentage")
    assert list(fig.data[0].y) == [200.0, 500.0]
