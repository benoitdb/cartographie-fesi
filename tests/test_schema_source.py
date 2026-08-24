"""Garde-fous sur le fichier source (issues #45 et #47).

Ces tests couvrent les deux façons dont le pipeline peut produire des données
fausses sans lever d'erreur : lire le mauvais millésime, ou lire les bonnes
colonnes au mauvais endroit. Ce sont les cas les plus coûteux du projet, parce
que rien en aval ne les signale.
"""

import pytest
from schema_source import (
    COLONNES_2021_2027,
    SCHEMAS,
    SchemaSourceError,
    build_cols,
    millesime_du_fichier,
    normalise_libelle,
    schema_de_periode,
)

LIBELLES_REELS = [libelle for _, libelle in COLONNES_2021_2027]
LIBELLES_2014_2020 = [libelle for _, libelle in SCHEMAS["2014-2020"]]


def test_les_colonnes_attendues_donnent_le_mapping_complet():
    cols = build_cols(LIBELLES_REELS)

    assert set(cols) == {cle for cle, _ in COLONNES_2021_2027}
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


# Les 19 colonnes du fichier Synergie, **relevées dans le fichier** et recopiées
# ici à la main. C'est volontairement une seconde saisie : les autres tests
# dérivent leurs libellés du schéma lui-même et ne peuvent donc pas voir une
# transcription fausse — vérifié par mutation (deux entrées interverties dans
# `SCHEMAS` ne faisaient rougir aucun test). Seule cette liste indépendante
# attrape le cas, sans avoir besoin du XLSX, absent de la CI.
LIBELLES_SYNERGIE_RELEVES = [
    "Numéro Opération",
    "NumCCI",
    "Libellé programme",
    "Intitulé du projet",
    "Résumé de l'opération",
    "Nom du bénéficiaire",
    "Code postal du bénéficiaire",
    "Date de début de l'opération",
    "Date de fin de l'opération",
    "Code postal de l’opération",
    "Zone",
    "Département de l’opération",
    "Région de l'opération",
    "Pays",
    "Domaine d’intervention",
    "Date de programmation",
    "Fonds",
    "Total des dépenses éligibles programmées",
    "Montant UE programmé",
]


def test_le_schema_2014_2020_decrit_le_fichier_reel():
    """Le schéma est comparé à un relevé indépendant des colonnes du fichier :
    une clé interne posée en face de la mauvaise colonne mapperait les montants à
    l'envers, sans que rien ne le signale."""
    cols = build_cols(LIBELLES_SYNERGIE_RELEVES, schema=SCHEMAS["2014-2020"])

    assert cols["montant_ue"] == "Montant UE programmé"
    assert cols["depenses"] == "Total des dépenses éligibles programmées"
    assert cols["fonds"] == "Fonds"
    assert cols["region"] == "Région de l'opération"
    assert cols["libelle_prog"] == "Libellé programme"


def test_le_schema_2014_2020_donne_le_mapping_complet():
    """La période a ses propres colonnes : 19 au lieu de 23, dans un autre ordre,
    avec le `Domaine d'intervention` et la date de programmation à la place des
    objectifs stratégiques et de la première convention (issue #12)."""
    cols = build_cols(LIBELLES_2014_2020, schema=SCHEMAS["2014-2020"])

    assert cols["montant_ue"] == "Montant UE programmé"
    assert cols["depenses"] == "Total des dépenses éligibles programmées"
    assert cols["domaine_intervention"] == "Domaine d’intervention"
    assert cols["date_programmation"] == "Date de programmation"
    # Les colonnes absentes de la période ne sont pas inventées : le code aval
    # doit tester la présence de la clé (`objectif_strat` conditionne des blocs
    # d'agrégats entiers), pas la supposer.
    assert "objectif_strat" not in cols
    assert "date_convention" not in cols
    assert "taux_cofinance" not in cols


def test_un_fichier_2014_2020_reordonne_est_refuse_en_nommant_la_position():
    """Le garde-fou vaut pour les deux périodes : ici l'inversion des deux
    montants, celle qui ne casse rien en aval et fausse tout."""
    colonnes = list(LIBELLES_2014_2020)
    i, j = 17, 18  # dépenses éligibles <-> montant UE
    colonnes[i], colonnes[j] = colonnes[j], colonnes[i]

    with pytest.raises(SchemaSourceError) as erreur:
        build_cols(colonnes, schema=SCHEMAS["2014-2020"])

    assert "position 17" in str(erreur.value)


def test_le_fichier_2014_2020_est_refuse_par_le_schema_2021_2027():
    """Vérifier un fichier contre le schéma de l'autre période doit échouer, pas
    mapper au hasard : les deux fichiers partagent des libellés (`Fonds`,
    `Pays`), à des positions différentes."""
    with pytest.raises(SchemaSourceError):
        build_cols(LIBELLES_2014_2020)


def test_le_defaut_de_build_cols_reste_2021_2027():
    """Le défaut historique ne bouge pas : le générateur de fixture et tout code
    appelant sans `schema` continuent de viser la source du dashboard."""
    assert build_cols(LIBELLES_REELS) == build_cols(
        LIBELLES_REELS, schema=SCHEMAS["2021-2027"]
    )


def test_une_periode_inconnue_liste_les_periodes_connues():
    with pytest.raises(SchemaSourceError) as erreur:
        schema_de_periode("2028-2034")

    assert "2021-2027" in str(erreur.value)


def test_normalise_libelle_conserve_les_accents():
    """Les accents sont stables dans les exports successifs, contrairement aux
    apostrophes : les neutraliser ferait passer "Region" pour "Région"."""
    assert normalise_libelle("Région") != normalise_libelle("Region")


def test_le_millesime_est_extrait_du_prefixe_du_nom_de_fichier(tmp_path):
    """Cette date est propagée jusqu'au dashboard, qui l'affiche (issue #47) :
    une erreur ici afficherait une fraîcheur fausse, pire que pas de date."""
    fichier = tmp_path / "20260316_liste_operations_conventionnees_FEDER_FSE_FTJ_0.xlsx"

    assert millesime_du_fichier(fichier) == "2026-03-16"


def test_un_fichier_renomme_a_la_main_reste_exploitable_sans_millesime(tmp_path):
    """None, pas une exception : le pipeline doit continuer de tourner sur un
    fichier renommé — il perd seulement l'affichage de sa date."""
    assert millesime_du_fichier(tmp_path / "liste_operations_conventionnees.xlsx") is None
