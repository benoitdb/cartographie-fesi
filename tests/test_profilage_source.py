"""Profil d'une source : les chiffres qui attestent qu'une donnée a été validée.

`profiler_source` (data-pipeline/profilage_source.py) produit le profil affiché
par la page « Validation de la source » (issue #69). Une erreur ici ne lève
aucune exception : elle affiche une complétude, un taux de cofinancement ou une
part de fonds *faux* avec l'aplomb d'un chiffre juste — exactement ce qu'on
montre pour rassurer. D'où des cas construits, valeurs attendues posées à la
main.

Le cas de référence reproduit en miniature les particularités réelles de la
source 2014-2020 : région peu remplie mais dérivable du programme, dimension
thématique vide à 100 %, une date illisible, un montant UE négatif, une clé
dupliquée.
"""

import pandas as pd
import pytest
from profilage_source import profiler_source

COLS = {
    "numero_operation": "num",
    "programme": "prog",
    "beneficiaire": "benef",
    "fonds": "fonds",
    "region": "region",
    "departement": "dep",
    "dimension_thematique": "domaine",
    "date_programmation": "date",
    "montant_ue": "ue",
    "depenses": "depenses",
    "pays": "pays",
}


@pytest.fixture
def df():
    return pd.DataFrame([
        # num, prog, benef, fonds, region, dep, domaine, date, ue, depenses, pays
        ("N1", "PA", "B1", "FEDER", "Occitanie", "D1", None, "2015-03-01", 100, 200, "FRA"),
        ("N2", "PA", "B2", "FEDER", None, None, None, "2015-07-01", 300, 500, "FRA"),
        ("N3", "PA", "B3", "FSE", "Occitanie", "D3", None, "2016-01-01", 50, 100, "FRA"),
        ("N4", "PN", "B4", "FEAD", None, None, None, "pas une date", 20, 40, "FRA"),
        ("N5", "PN", "B5", "FEAD", None, None, None, "2016-05-01", -10, 30, "FRA"),
        ("N1", "PA", "B6", "FEDER", None, None, None, "2015-09-01", 40, 60, "FRA"),
    ], columns=["num", "prog", "benef", "fonds", "region", "dep", "domaine", "date", "ue", "depenses", "pays"])


def test_volumetrie(df):
    profil = profiler_source(df, COLS)
    assert profil["volumetrie"] == {"operations": 6, "colonnes": 11}


def test_completude_compte_les_valeurs_presentes(df):
    comp = profiler_source(df, COLS)["completude"]
    assert comp["numero_operation"]["taux"] == 100.0
    assert comp["region"]["remplis"] == 2
    assert comp["region"]["taux"] == 33.3  # 2/6
    # Une date illisible reste *présente* : la complétude ne juge pas la
    # lisibilité (c'est le rôle de la section `dates`).
    assert comp["date_programmation"]["taux"] == 100.0


def test_par_fonds_trie_par_montant_decroissant(df):
    par_fonds = profiler_source(df, COLS)["par_fonds"]
    assert [f["fonds"] for f in par_fonds] == ["FEDER", "FSE", "FEAD"]
    feder = par_fonds[0]
    assert feder["nb"] == 3
    assert feder["montant_ue"] == 440.0  # 100 + 300 + 40
    assert feder["part_montant"] == 88.0  # 440 / 500


def test_montants_et_cofinancement(df):
    montants = profiler_source(df, COLS)["montants"]
    assert montants["montant_ue_total"] == 500.0
    assert montants["depenses_total"] == 930.0
    assert montants["cofinancement_global"] == 53.8  # 100 * 500 / 930
    assert montants["montants_ue_negatifs"] == 1


def test_cle_repere_les_doublons(df):
    cle = profiler_source(df, COLS)["cle"]
    assert cle["distincts"] == 5  # N1 compté une fois
    assert cle["doublons"] == 1


def test_dimension_thematique_vide_a_100pct(df):
    dim = profiler_source(df, COLS)["dimension_thematique"]
    assert dim["taux_remplie"] == 0.0
    assert dim["distincts"] == 0
    assert dim["top"] == []


def test_dates_separe_illisibles_et_ventile_par_annee(df):
    dates = profiler_source(df, COLS)["dates"]
    assert dates["illisibles"] == 1
    assert dates["annee_min"] == 2015
    assert dates["annee_max"] == 2016
    assert dates["par_annee"] == {"2015": 3, "2016": 2}


def test_region_derivable_distingue_national_du_regional(df):
    deriver = {"PA": "Occitanie", "PN": None}.get
    rd = profiler_source(df, COLS, deriver_region=deriver)["region_derivable"]
    assert rd["programmes_distincts"] == 2
    assert rd["programmes_avec_region"] == 1
    assert rd["operations_resolues"] == 4  # les 4 opérations du programme PA
    assert rd["taux_operations_resolues"] == 66.7
    # PN (national) listé sans être qualifié d'erreur.
    assert rd["programmes_sans_region_unique"] == ["PN"]


def test_regions_ventile_les_manquantes_par_fonds(df):
    regions = profiler_source(df, COLS)["regions"]
    assert regions["taux_colonne_remplie"] == 33.3
    manquantes = {ligne["valeur"]: ligne["nb"] for ligne in regions["manquantes_par_fonds"]}
    assert manquantes == {"FEDER": 2, "FEAD": 2}  # N2/N1 (FEDER), N4/N5 (FEAD)


def test_section_absente_si_cle_non_mappee(df):
    """Une clé sémantique absente de `cols` retire sa section, sans planter :
    les périodes n'ont pas toutes les mêmes champs."""
    cols_sans_montants = {k: v for k, v in COLS.items() if k not in ("montant_ue", "depenses")}
    profil = profiler_source(df, cols_sans_montants)
    assert "montants" not in profil
    assert profil["par_fonds"][0]["montant_ue"] is None


def test_region_derivable_absente_sans_deriver(df):
    assert "region_derivable" not in profiler_source(df, COLS)
