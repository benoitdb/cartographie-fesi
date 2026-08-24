"""Le mapping de colonnes de chaque source profilée (data-pipeline/profil_source.py).

`profiler_source` est pure et ne connaît que des clés sémantiques : c'est le
descripteur de source qui décide quelle colonne réelle porte le montant UE ou le
fonds. Une erreur ici ne lève rien — elle profile la mauvaise colonne et affiche
un chiffre faux sur la page qui sert précisément à attester que la donnée a été
vérifiée (issue #69).

2021-2027 ne recopie pas ses libellés : elle les tire de
`schema_source.build_cols`, le garde-fou déjà utilisé par `ingest.py` (issue #45).
Ces tests vérifient que la traduction vers les clés sémantiques est juste, et que
le garde-fou reste bien armé au passage.
"""

import pandas as pd
import pytest
from profil_source import SOURCES, cols_2021_2027
from schema_source import COLONNES_ATTENDUES, SchemaSourceError

# Les clés dont dépendent les sections du profil affichées par la page.
CLES_ATTENDUES = {
    "numero_operation", "programme", "beneficiaire", "fonds", "region",
    "departement", "dimension_thematique", "date_programmation", "montant_ue",
    "depenses", "pays",
}


@pytest.fixture
def df_2021_2027():
    """Une ligne vide aux libellés réels de la source 2021-2027 : seul l'ordre
    des colonnes compte pour `build_cols`."""
    libelles = [libelle for _, libelle in COLONNES_ATTENDUES]
    return pd.DataFrame([[None] * len(libelles)], columns=libelles)


def test_cols_2021_2027_couvre_toutes_les_cles(df_2021_2027):
    assert set(cols_2021_2027(df_2021_2027)) == CLES_ATTENDUES


def test_cols_2021_2027_pointe_les_bonnes_colonnes(df_2021_2027):
    """Les correspondances qu'une inversion rendrait fausses sans rien casser :
    montant UE contre dépenses éligibles, et la date de référence de la période
    (première convention — il n'y a pas de date de programmation ici)."""
    cols = cols_2021_2027(df_2021_2027)
    assert cols["montant_ue"] == "Montant UE"
    assert cols["depenses"] == "Total des dépenses éligibles"
    assert cols["date_programmation"] == "Date première convention"
    assert cols["dimension_thematique"] == "Objectif stratégique"
    assert cols["programme"] == "Libellé Programme"


def test_cols_2021_2027_suit_les_libelles_reels(df_2021_2027):
    """Le mapping se fait par index : un libellé retypographié par l'export
    (apostrophe droite → typographique) doit être suivi, pas rejeté ni figé sur
    l'ancienne graphie."""
    renomme = df_2021_2027.rename(
        columns={"Département de l'opération": "Département de l’opération"}
    )
    assert cols_2021_2027(renomme)["departement"] == "Département de l’opération"


def test_cols_2021_2027_echoue_si_la_source_est_reordonnee(df_2021_2027):
    """Le garde-fou de `ingest.py` doit valoir aussi pour le profil : sans lui,
    un réordonnancement produirait un profil faux avec un code de sortie 0."""
    colonnes = list(df_2021_2027.columns)
    colonnes[19], colonnes[21] = colonnes[21], colonnes[19]  # dépenses ↔ montant UE
    with pytest.raises(SchemaSourceError):
        cols_2021_2027(df_2021_2027.set_axis(colonnes, axis=1))


def test_chaque_source_declare_les_cles_attendues():
    """Garde-fou sur les descripteurs : une source ajoutée en oubliant une clé
    perdrait silencieusement une section entière du profil (`profiler_source`
    désactive plutôt que d'échouer, par conception)."""
    for source_id, conf in SOURCES.items():
        cols = conf["cols"]
        if callable(cols):
            continue  # couvert par les tests ci-dessus
        assert set(cols) == CLES_ATTENDUES, f"clés manquantes pour {source_id}"
