"""Les descripteurs de source (data-pipeline/sources.py).

Un descripteur décrit un fichier une fois pour deux lecteurs : `ingest.py`, qui
en fait `data.json`, et `profil_source.py`, qui en fait le rapport affiché par la
page « Validation de la source ». Une erreur ici ne lève rien — elle fait lire la
mauvaise feuille, la mauvaise colonne ou le mauvais millésime, et le profil
atteste alors une donnée qui n'est pas celle qu'on a ingérée (issues #69, #12).

Ce fichier reprend aussi les tests du choix du fichier source, qui vivaient dans
`test_schema_source.py` : le motif de nom appartient désormais au descripteur.
"""

import pandas as pd
import pytest
from schema_source import SCHEMAS, SchemaSourceError
from sources import (
    SOURCES,
    cols_internes,
    cols_profil,
    millesime,
    source,
    trouver_fichier,
)

# Les clés dont dépendent les sections du profil affichées par la page.
CLES_PROFIL_ATTENDUES = {
    "numero_operation", "programme", "beneficiaire", "fonds", "region",
    "departement", "dimension_thematique", "date_programmation", "montant_ue",
    "depenses", "pays",
}


def colonnes_de(source_id):
    """Les libellés réels de la source, dans l'ordre du fichier : seul l'ordre
    compte pour le mapping par index. `schema` prime sur `periode` quand le
    descripteur le déclare (issue #68 : plusieurs fichiers d'une période peuvent
    avoir des colonnes différentes) — même repli que `sources.cols_internes`."""
    conf = SOURCES[source_id]
    return [libelle for _, libelle in SCHEMAS[conf.get("schema", conf["periode"])]]


def df_vide(source_id):
    colonnes = colonnes_de(source_id)
    return pd.DataFrame([[None] * len(colonnes)], columns=colonnes)


# --- Choix du fichier ------------------------------------------------------


def test_le_millesime_le_plus_recent_est_retenu(tmp_path):
    """Les noms sont datés, donc l'ordre alphabétique est l'ordre chronologique :
    déposer un nouvel export doit suffire (issue #47)."""
    for nom in [
        "20250601_liste_operations_conventionnees_FEDER_FSE_FTJ_0.xlsx",
        "20260316_liste_operations_conventionnees_FEDER_FSE_FTJ_0.xlsx",
        "20251115_liste_operations_conventionnees_FEDER_FSE_FTJ_0.xlsx",
    ]:
        (tmp_path / nom).touch()

    conf = source("2021-2027-conventionnees")
    assert trouver_fichier(conf, tmp_path).name.startswith("20260316")


def test_absence_de_fichier_source_leve_une_erreur_qui_dit_ou_le_trouver(tmp_path):
    with pytest.raises(SchemaSourceError) as erreur:
        trouver_fichier(source("2021-2027-conventionnees"), tmp_path)

    assert "europe-en-france.gouv.fr" in str(erreur.value)


def test_les_motifs_des_deux_sources_ne_se_recouvrent_pas(tmp_path):
    """Les deux fichiers cohabitent dans `data/raw/`. Un motif qui attrape aussi
    celui de l'autre période ne se voit pas tout de suite : c'est l'ordre
    alphabétique qui décide, et il peut rendre le bon fichier aujourd'hui puis le
    mauvais au prochain export. On vérifie donc que chaque motif ne **matche**
    qu'un fichier, pas seulement qu'il retourne le bon."""
    fichiers = [
        "20260316_liste_operations_conventionnees_FEDER_FSE_FTJ_0.xlsx",
        "20270415_liste_operations_conventionnees_FEDER_FSE_FTJ_0.xlsx",
        "liste_operations_synergie_1420_08_2023.xlsx",
        "pon_fse_2014_2020.xls",
    ]
    for nom in fichiers:
        (tmp_path / nom).touch()

    attendus = {
        "2021-2027-conventionnees": 2,  # deux millésimes du même fichier
        "2014-2020-synergie": 1,
        "2014-2020-pon-fse": 1,
    }
    for source_id, conf in SOURCES.items():
        matches = sorted(p.name for p in tmp_path.glob(conf["motif_fichier"]))
        assert len(matches) == attendus[source_id], f"{source_id} attrape {matches}"

    assert trouver_fichier(source("2021-2027-conventionnees"), tmp_path).name.startswith(
        "20270415"
    )
    assert trouver_fichier(source("2014-2020-synergie"), tmp_path).name.startswith(
        "liste_operations_synergie"
    )


def test_une_source_inconnue_liste_les_sources_connues():
    with pytest.raises(SchemaSourceError) as erreur:
        source("2014-2020-hors-synergie")

    assert "2021-2027-conventionnees" in str(erreur.value)


# --- Mapping des colonnes --------------------------------------------------


# Sources dont le fichier porte toutes les colonnes du profil (les deux
# premières sources du pipeline). Les sources hors-Synergie ajoutées depuis
# (issue #68) ont des colonnes réellement absentes — codes postaux, département,
# pays, dimension thématique — et ne peuvent donc pas viser cet ensemble complet
# sans mapper une clé de profil vers une colonne qui n'existe pas.
SOURCES_A_SCHEMA_COMPLET = {"2021-2027-conventionnees", "2014-2020-synergie"}


@pytest.mark.parametrize("source_id", sorted(SOURCES_A_SCHEMA_COMPLET))
def test_chaque_source_a_schema_complet_couvre_toutes_les_cles_du_profil(source_id):
    """Une source ajoutée en oubliant une clé perdrait silencieusement une
    section entière du profil (`profiler_source` désactive plutôt que d'échouer,
    par conception)."""
    assert set(cols_profil(SOURCES[source_id], colonnes_de(source_id))) == (
        CLES_PROFIL_ATTENDUES
    )


@pytest.mark.parametrize("source_id", sorted(set(SOURCES) - SOURCES_A_SCHEMA_COMPLET))
def test_chaque_source_partielle_ne_declare_que_des_cles_de_profil_connues(source_id):
    """Une source à schéma partiel (issue #68) peut couvrir un sous-ensemble des
    clés de profil, mais pas en inventer une : une clé absente de
    `CLES_PROFIL_ATTENDUES` serait un profil que `profiler_source` ne sait pas
    afficher."""
    cles = set(cols_profil(SOURCES[source_id], colonnes_de(source_id)))
    assert cles <= CLES_PROFIL_ATTENDUES
    assert cles, "une source ne devrait pas déclarer un profil vide"


def test_le_profil_2021_2027_pointe_les_bonnes_colonnes():
    """Les correspondances qu'une inversion rendrait fausses sans rien casser :
    montant UE contre dépenses éligibles, et la date de référence de la période
    (première convention — il n'y a pas de date de programmation ici)."""
    cols = cols_profil(source("2021-2027-conventionnees"), colonnes_de("2021-2027-conventionnees"))

    assert cols["montant_ue"] == "Montant UE"
    assert cols["depenses"] == "Total des dépenses éligibles"
    assert cols["date_programmation"] == "Date première convention"
    assert cols["dimension_thematique"] == "Objectif stratégique"
    assert cols["programme"] == "Libellé Programme"


def test_le_profil_2014_2020_pointe_les_bonnes_colonnes():
    """Même clés sémantiques, colonnes différentes : la dimension thématique est
    le `Domaine d'intervention`, et la date de référence celle de la
    programmation. Confondre les deux périodes ici afficherait des libellés faux
    sur la page de validation."""
    cols = cols_profil(source("2014-2020-synergie"), colonnes_de("2014-2020-synergie"))

    assert cols["montant_ue"] == "Montant UE programmé"
    assert cols["depenses"] == "Total des dépenses éligibles programmées"
    assert cols["date_programmation"] == "Date de programmation"
    assert cols["dimension_thematique"] == "Domaine d’intervention"
    assert cols["programme"] == "Libellé programme"


def test_les_libelles_reels_sont_suivis_pas_recopies():
    """Le mapping se fait par index : un libellé retypographié par l'export
    (apostrophe droite → typographique) doit être suivi, pas rejeté ni figé sur
    l'ancienne graphie."""
    colonnes = colonnes_de("2021-2027-conventionnees")
    colonnes[11] = "Département de l’opération"  # était l'apostrophe droite

    cols = cols_profil(source("2021-2027-conventionnees"), colonnes)

    assert cols["departement"] == "Département de l’opération"


@pytest.mark.parametrize("source_id", list(SOURCES))
def test_une_source_reordonnee_fait_echouer_le_profil(source_id):
    """Le garde-fou d'`ingest.py` vaut aussi pour le profil : sans lui, un
    réordonnancement produirait un rapport faux avec un code de sortie 0."""
    colonnes = colonnes_de(source_id)
    colonnes[0], colonnes[1] = colonnes[1], colonnes[0]

    with pytest.raises(SchemaSourceError):
        cols_profil(SOURCES[source_id], colonnes)


def test_ingest_et_profil_lisent_la_meme_colonne():
    """Les deux lecteurs partent du même descripteur : ce qu'`ingest.py` compte
    comme montant UE doit être ce que le profil profile comme montant UE — sinon
    la page de validation atteste une donnée qui n'est pas celle du dashboard."""
    conf = source("2021-2027-conventionnees")
    colonnes = colonnes_de("2021-2027-conventionnees")

    internes = cols_internes(conf, colonnes)
    profil = cols_profil(conf, colonnes)

    assert profil["montant_ue"] == internes["montant_ue"]
    assert profil["region"] == internes["region"]


def test_un_df_reel_passe_le_mapping():
    """`cols_profil` reçoit un `df.columns` en production, pas une liste."""
    conf = source("2014-2020-synergie")
    assert cols_profil(conf, df_vide("2014-2020-synergie").columns)["fonds"] == "Fonds"


# --- Millésime -------------------------------------------------------------


def test_le_millesime_declare_prime_pour_une_source_sans_nom_date(tmp_path):
    """Le fichier Synergie n'a pas de préfixe daté : sans la date déclarée dans
    le descripteur, les données 14-20 arriveraient au dashboard sans millésime et
    la barre latérale n'afficherait rien (issue #47)."""
    conf = source("2014-2020-synergie")
    chemin = tmp_path / "liste_operations_synergie_1420_08_2023.xlsx"

    assert millesime(conf, chemin) == "2023-08-30"


def test_le_millesime_2021_2027_vient_du_nom_de_fichier(tmp_path):
    """Cette source ne déclare pas de date : elle est republiée 5 fois par an et
    seul le nom du fichier dit lequel des exports on lit."""
    conf = source("2021-2027-conventionnees")
    chemin = tmp_path / "20260316_liste_operations_conventionnees_FEDER_FSE_FTJ_0.xlsx"

    assert millesime(conf, chemin) == "2026-03-16"
