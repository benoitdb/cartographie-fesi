"""Le bloc `metadata` écrit par `ingest.py`, et la sortie choisie par source.

`metadata` est ce que le dashboard lit pour se décrire lui-même : le millésime
affiché en pied de barre latérale (issue #47), la période, les volumes. Une
erreur ici ne lève rien — elle affiche une fraîcheur ou une période fausse, ce
qui est pire que rien du tout.

Les tests portent sur des DataFrames construits à la main : aucun ne lit le XLSX,
absent de la CI.
"""

from pathlib import Path

import pandas as pd
import pytest
from agregats import calculer_agregats, partitionner
from ingest import SOURCE_PAR_DEFAUT, construire_metadata
from sources import SOURCES, source

COLS_2021_2027 = {
    "numero_op": "Numéro Opération",
    "libelle_prog": "Libellé Programme",
    "region": "Région de l'opération",
    "fonds": "Fonds",
    "objectif_strat": "Objectif stratégique",
    "montant_ue": "Montant UE",
    "depenses": "Total des dépenses éligibles",
}
COLS_2014_2020 = {
    cle: valeur for cle, valeur in COLS_2021_2027.items() if cle != "objectif_strat"
}


def df_deux_operations(avec_objectif=True):
    lignes = [
        {
            "Numéro Opération": "A",
            "Libellé Programme": "Un programme",
            "Région de l'opération": "76/Occitanie",
            "Fonds": "FEDER",
            "Objectif stratégique": "OS1",
            "Montant UE": 100.0,
            "Total des dépenses éligibles": 200.0,
            "regions_modernes": ["Occitanie"],
            "is_interregional": False,
            "is_national": False,
        },
        {
            "Numéro Opération": "B",
            "Libellé Programme": "Un programme national",
            "Région de l'opération": None,
            "Fonds": "FSE+",
            "Objectif stratégique": "OS2",
            "Montant UE": 10.0,
            "Total des dépenses éligibles": 20.0,
            "regions_modernes": [],
            "is_interregional": False,
            "is_national": True,
        },
    ]
    df = pd.DataFrame(lignes)
    return df if avec_objectif else df.drop(columns=["Objectif stratégique"])


def metadata_pour(source_id, avec_objectif, nom_fichier):
    conf = source(source_id)
    cols = COLS_2021_2027 if avec_objectif else COLS_2014_2020
    df = df_deux_operations(avec_objectif)
    partitions = partitionner(df)
    agregats = calculer_agregats(df, cols, partitions)
    return construire_metadata(df, cols, conf, Path(nom_fichier), agregats, partitions)


def test_la_periode_est_ecrite_pour_chaque_source():
    """Sans elle, rien dans le fichier ne dit de quelle programmation il parle —
    et le sélecteur de période côté dashboard n'aurait rien à lire."""
    assert metadata_pour(SOURCE_PAR_DEFAUT, True, "20260316_x.xlsx")["periode"] == "2021-2027"
    assert (
        metadata_pour("2014-2020-synergie", False, "liste_operations_synergie_x.xlsx")["periode"]
        == "2014-2020"
    )


def test_le_millesime_2014_2020_vient_de_la_date_declaree():
    """Le fichier Synergie n'a pas de préfixe daté : sans la date déclarée par le
    descripteur, la barre latérale n'afficherait rien pour cette période."""
    meta = metadata_pour("2014-2020-synergie", False, "liste_operations_synergie_1420_08_2023.xlsx")

    assert meta["millesime"] == "2023-08-30"
    assert meta["fichier_source"] == "liste_operations_synergie_1420_08_2023.xlsx"


def test_sans_dimension_thematique_la_metadata_le_dit_explicitement():
    """`dimension_thematique: None` déclaré, plutôt qu'un compte à 0 ou une clé
    silencieusement absente : la source n'a pas cette dimension, elle ne l'a pas
    mesurée à zéro."""
    meta = metadata_pour("2014-2020-synergie", False, "liste_operations_synergie_x.xlsx")

    assert meta["dimension_thematique"] is None
    assert "nb_objectifs_strategiques" not in meta


def test_avec_dimension_thematique_le_compte_est_conserve():
    """Non-régression : 2021-2027 garde exactement les clés qu'elle avait."""
    meta = metadata_pour(SOURCE_PAR_DEFAUT, True, "20260316_x.xlsx")

    assert meta["nb_objectifs_strategiques"] == 2
    assert "dimension_thematique" not in meta


def test_les_volumes_decrivent_bien_le_jeu_ingere():
    meta = metadata_pour(SOURCE_PAR_DEFAUT, True, "20260316_x.xlsx")

    assert meta["total_operations"] == 2
    assert meta["nb_fonds"] == 2
    assert meta["nb_regions_harmonized"] == 1  # l'opération nationale n'est pas une région
    assert meta["partitions"] == {"mono_region": 1, "interregional": 0, "national": 1}


def test_chaque_source_ecrit_dans_son_propre_fichier():
    """Deux sources qui déclareraient la même sortie s'écraseraient l'une
    l'autre à chaque régénération, sans la moindre erreur."""
    sorties = [conf["fichier_sortie"] for conf in SOURCES.values()]

    assert len(sorties) == len(set(sorties))


def test_la_sortie_par_defaut_reste_data_json():
    """Le dashboard lit `data.json` ; le renommer sans le savoir viderait les
    4 pages existantes."""
    assert source(SOURCE_PAR_DEFAUT)["fichier_sortie"] == "data.json"
    assert source("2014-2020-synergie")["fichier_sortie"] == "data_2014-2020.json"


@pytest.mark.parametrize("source_id", list(SOURCES))
def test_chaque_source_declare_les_champs_dont_ingest_a_besoin(source_id):
    """Une source ajoutée en oubliant un champ échouerait au milieu d'une
    ingestion de plusieurs minutes, après lecture du XLSX."""
    conf = SOURCES[source_id]

    for champ in ("label", "periode", "motif_fichier", "feuille", "fichier_sortie",
                  "programme_to_region", "cles_profil", "url_source"):
        assert champ in conf, f"{source_id} : champ {champ!r} manquant"
