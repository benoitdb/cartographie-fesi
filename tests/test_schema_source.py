"""Garde-fous sur le fichier source (issues #45 et #47).

Ces tests couvrent les deux façons dont le pipeline peut produire des données
fausses sans lever d'erreur : lire le mauvais millésime, ou lire les bonnes
colonnes au mauvais endroit. Ce sont les cas les plus coûteux du projet, parce
que rien en aval ne les signale.
"""

import pytest
from schema_source import (
    COLONNES_ATTENDUES,
    SchemaSourceError,
    build_cols,
    millesime_du_fichier,
    normalise_libelle,
    trouver_fichier_source,
)

LIBELLES_REELS = [libelle for _, libelle in COLONNES_ATTENDUES]


def test_les_colonnes_attendues_donnent_le_mapping_complet():
    cols = build_cols(LIBELLES_REELS)

    assert set(cols) == {cle for cle, _ in COLONNES_ATTENDUES}
    assert cols["region"] == "Région de l'opération"
    assert cols["montant_ue"] == "Montant UE"


def test_deux_colonnes_interverties_sont_refusees():
    """Le cas qui motive tout ce module : deux colonnes échangées passent
    inaperçues avec un mapping par index seul, et attribuent silencieusement les
    montants UE aux dépenses éligibles."""
    colonnes = list(LIBELLES_REELS)
    i, j = 19, 21  # Total des dépenses éligibles <-> Montant UE
    colonnes[i], colonnes[j] = colonnes[j], colonnes[i]

    with pytest.raises(SchemaSourceError) as erreur:
        build_cols(colonnes)

    assert "position 19" in str(erreur.value)


def test_une_colonne_inseree_est_refusee():
    colonnes = list(LIBELLES_REELS)
    colonnes.insert(5, "Nouvelle colonne ajoutée par la source")

    with pytest.raises(SchemaSourceError) as erreur:
        build_cols(colonnes)

    assert "position 5" in str(erreur.value)


def test_un_fichier_trop_court_est_refuse():
    with pytest.raises(SchemaSourceError, match="colonnes"):
        build_cols(LIBELLES_REELS[:10])


def test_des_colonnes_supplementaires_a_la_fin_sont_tolerees():
    """Une colonne ajoutée après les colonnes connues ne décale rien : le
    pipeline reste correct, il n'y a pas de raison de le bloquer."""
    cols = build_cols([*LIBELLES_REELS, "Colonne ajoutée en fin de fichier"])

    assert cols["date_convention"] == "Date première convention"


@pytest.mark.parametrize(
    "variante",
    [
        "Région de l’opération",  # apostrophe typographique U+2019
        "Région de l'opération ",  # espace en fin
        "Région  de  l'opération",  # espaces doublés
        "RÉGION DE L'OPÉRATION",  # casse
    ],
)
def test_les_variantes_typographiques_du_meme_libelle_sont_acceptees(variante):
    """Le fichier source mélange déjà les deux apostrophes. Échouer sur une
    normalisation typographique de l'export serait un faux positif : ce n'est
    pas le problème qu'on cherche à détecter."""
    colonnes = list(LIBELLES_REELS)
    colonnes[12] = variante

    assert build_cols(colonnes)["region"] == variante


def test_normalise_libelle_conserve_les_accents():
    """Les accents sont stables dans les exports successifs, contrairement aux
    apostrophes : les neutraliser ferait passer "Region" pour "Région"."""
    assert normalise_libelle("Région") != normalise_libelle("Region")


def test_le_millesime_le_plus_recent_est_retenu(tmp_path):
    for nom in [
        "20250601_liste_operations_conventionnees_FEDER_FSE_FTJ_0.xlsx",
        "20260316_liste_operations_conventionnees_FEDER_FSE_FTJ_0.xlsx",
        "20251115_liste_operations_conventionnees_FEDER_FSE_FTJ_0.xlsx",
    ]:
        (tmp_path / nom).touch()

    assert trouver_fichier_source(tmp_path).name.startswith("20260316")


def test_absence_de_fichier_source_leve_une_erreur_qui_dit_ou_le_trouver(tmp_path):
    with pytest.raises(SchemaSourceError) as erreur:
        trouver_fichier_source(tmp_path)

    assert "europe-en-france.gouv.fr" in str(erreur.value)


def test_le_millesime_est_extrait_du_prefixe_du_nom_de_fichier(tmp_path):
    """Cette date est propagée jusqu'au dashboard, qui l'affiche (issue #47) :
    une erreur ici afficherait une fraîcheur fausse, pire que pas de date."""
    fichier = tmp_path / "20260316_liste_operations_conventionnees_FEDER_FSE_FTJ_0.xlsx"

    assert millesime_du_fichier(fichier) == "2026-03-16"


def test_un_fichier_renomme_a_la_main_reste_exploitable_sans_millesime(tmp_path):
    """None, pas une exception : le pipeline doit continuer de tourner sur un
    fichier renommé — il perd seulement l'affichage de sa date."""
    assert millesime_du_fichier(tmp_path / "liste_operations_conventionnees.xlsx") is None
